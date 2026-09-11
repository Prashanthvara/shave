"""Load-shape archetypes behind one interface.

The scorer needs exactly two things from a building's load: what its monthly
billed peak is, and what the shape of its worst billed day looks like. It does
not need a full year of 15-minute data, and it must not care where the shape
came from.

That matters here because the two sources are not alike:

  ComStockArchetype  real 15-minute profiles from NREL's End-Use Load Profiles,
                     calibrated against utility meter data. Covers hospitals,
                     retail, warehouses, offices, schools, restaurants, hotels.

  ModeledArchetype   synthesised shift-schedule profiles. NREL ComStock models
                     exactly 14 commercial building types and names laboratories,
                     data centers, movie theaters and ice rinks as NOT modelled.
                     Against Powertown's published customer list that leaves
                     manufacturing, cold storage, machine shops, metal fab,
                     commercial laundries, labs, car dealerships and ice arenas
                     uncovered. Those are modelled, not measured, and every row
                     built this way is labelled `modeled` in the interface.

Two consequences of the seam. The scorer is unit-testable against hand-built
fixtures before any data pipeline exists. And it reads 52 points per month
rather than 35,040 per year, which is roughly 0.2% of what materialising full
profiles would cost.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

import numpy as np

from .assumptions import INTERVAL_MINUTES, PEAK_HOUR_END, PEAK_HOUR_START

Source = Literal["comstock", "modeled"]

INTERVALS_PER_BILLED_DAY = (PEAK_HOUR_END - PEAK_HOUR_START) * 60 // INTERVAL_MINUTES

#: Interval width in hours, and the full 24-hour grid at that resolution.
#: The full day lives here beside the billed window because it is a property
#: of the tariff interval, not of the modelled library. `modeled` re-exports
#: FULL_DAY_HOURS; defining it there would force this module to import that
#: one, which imports this one.
STEP_HOURS = INTERVAL_MINUTES / 60.0
INTERVALS_PER_DAY = int(round(24.0 / STEP_HOURS))
FULL_DAY_HOURS = np.arange(0.0, 24.0, STEP_HOURS)

# Massachusetts cooling-degree-day shape, normalised to its own max. Drives the
# seasonal scaling of cooling and refrigeration load. Jan through Dec.
MA_COOLING_SHAPE = np.array(
    [0.02, 0.02, 0.04, 0.10, 0.28, 0.66, 1.00, 0.94, 0.55, 0.18, 0.05, 0.02]
)


@runtime_checkable
class Archetype(Protocol):
    """What the scorer is allowed to ask for."""

    source: Source

    def monthly_peaks(self) -> np.ndarray:
        """Billed peak kW for each of the 12 months. Shape (12,)."""
        ...

    def peak_day_window(self, month: int) -> np.ndarray:
        """The worst billed day's load inside the peak window, in kW.

        `month` is 1-12. Shape (INTERVALS_PER_BILLED_DAY,).
        """
        ...

    def offpeak_max(self, month: int) -> float:
        """Highest load in the 21:00-08:00 recharge window, in kW.

        `month` is 1-12. The recharge headroom test reads this.
        """
        ...


def _jitter_offset(parcel_id: str, max_intervals: int = 2) -> int:
    """Deterministic per-parcel shift-start jitter, in intervals.

    Without this every modelled parcel of the same type peaks at the same
    minute, which makes any aggregate check meaningless and makes the map read
    as synthetic. Seeded by parcel id so a re-run reproduces exactly.
    """
    digest = hashlib.sha256(parcel_id.encode()).digest()
    span = 2 * max_intervals + 1
    return (digest[0] % span) - max_intervals


@dataclass
class ModeledArchetype:
    """A synthesised industrial profile, built from shape parameters.

    Parameters are the four numbers a measured industrial dataset supplies:
    load factor, hour of peak, spike duration, and the base/process split. They
    live in config so the values can be swapped for measured ones later without
    touching this code.
    """

    parcel_id: str
    peak_kw: float
    base_fraction: float = 0.30        # overnight load as a share of peak
    shift_start_hour: float = 6.5      # when the process block begins
    shift_end_hour: float = 15.0
    spike_minutes: float = 20.0        # startup ramp width
    spike_fraction: float = 0.55       # spike height above the process plateau
    refrigeration: bool = False        # adds a duty cycle and seasonal swing
    cooling_fraction: float = 0.18     # share of load that scales with weather

    source: Source = field(default="modeled", init=False)

    def _window_hours(self) -> np.ndarray:
        step = INTERVAL_MINUTES / 60.0
        return PEAK_HOUR_START + np.arange(INTERVALS_PER_BILLED_DAY) * step

    def _day_shape(
        self, day_type: str, month: int, hours: np.ndarray | None = None
    ) -> np.ndarray:
        """Normalised 0-1 load across `hours` for one day type.

        `hours` defaults to the billed window. `modeled.full_day_shape` passes
        a 24-hour grid so the magnitude chain measures the same shape the
        scorer reads, rather than a second implementation of it.
        """
        hours = self._window_hours() if hours is None else np.asarray(hours, dtype=float)

        # Jitter is a shift in TIME, not a roll of the array. A roll permutes
        # whichever grid it is handed, so the same parcel's peak could land
        # inside the billed window on the 52-point grid and outside it on the
        # 96-point one -- the window would not be a slice of the day, and the
        # full-day maximum that scales billed demand could not be compared
        # with it. Shifting the evaluation hours makes the shape one function
        # of clock time, identical on every grid.
        hours = hours - _jitter_offset(self.parcel_id) * STEP_HOURS
        base = np.full(hours.size, self.base_fraction)

        if day_type == "sunday":
            shape = base.copy()
        else:
            start = self.shift_start_hour
            end = self.shift_end_hour if day_type == "weekday" else self.shift_end_hour - 4.0
            process = np.where((hours >= start) & (hours < end), 1.0 - self.base_fraction, 0.0)
            if day_type == "saturday":
                process *= 0.55
            shape = base + process

            # Startup ramp. A sharp inrush at shift start is what makes a
            # machine shop shaveable and a hospital plateau not.
            if day_type == "weekday" and self.spike_fraction > 0:
                sigma = max(self.spike_minutes / 60.0, 1e-6) / 2.0
                shape = shape + self.spike_fraction * np.exp(
                    -(((hours - start) / sigma) ** 2)
                )

        if self.refrigeration:
            # Compressors cycling. Adds sawtooth on top of everything else.
            # Indexed by clock time, not array position: an index-based term
            # is a different function of time on each grid.
            shape = shape + 0.12 * np.abs(np.sin((hours / STEP_HOURS) * 1.1))

        # Weather-driven component, scaled by the month.
        seasonal = 1.0 + self.cooling_fraction * (MA_COOLING_SHAPE[month - 1] - 0.5)
        shape = shape * seasonal

        return np.clip(shape, 0.0, None)

    def _annual_max_shape(self) -> float:
        """The normalised annual maximum, measured over the FULL 24 hours.

        `peak_kw` is the building's true annual peak: `modeled.peak_kw_for`
        derives it by dividing annual energy by a load factor computed against
        the full-day peak. Scaling the billed window by a window-only maximum
        would silently redefine the same number as the *billed* peak, and
        inflate billed demand wherever a building's real peak falls outside
        08:00-21:00 -- 1.55x for a machine shop whose shift starts at 06:30,
        1.22x for a cold store starting at 06:00.

        An unbilled peak must never set billed magnitude. That is the same
        rule the measured half already follows, where the reducers mask to
        billed intervals before taking a monthly maximum.
        """
        return max(
            float(self._day_shape("weekday", m, hours=FULL_DAY_HOURS).max())
            for m in range(1, 13)
        )

    def peak_day_window(self, month: int) -> np.ndarray:
        if not 1 <= month <= 12:
            raise ValueError(f"month must be 1-12, got {month}")
        shape = self._day_shape("weekday", month)
        if shape.max() <= 0:
            return np.zeros(INTERVALS_PER_BILLED_DAY)
        annual_max = self._annual_max_shape()
        if annual_max <= 0:
            return np.zeros(INTERVALS_PER_BILLED_DAY)
        return shape * (self.peak_kw / annual_max)

    def offpeak_max(self, month: int) -> float:
        """Highest load in the 21:00-08:00 recharge window, in kW.

        Uses the weekday shape: a weekday night is the one that has to absorb
        the recharge, and it carries the highest base of the three day types.
        """
        if not 1 <= month <= 12:
            raise ValueError(f"month must be 1-12, got {month}")
        shape = self._day_shape("weekday", month, hours=FULL_DAY_HOURS)
        night = (FULL_DAY_HOURS >= PEAK_HOUR_END) | (FULL_DAY_HOURS < PEAK_HOUR_START)
        # Same denominator as peak_day_window, so the overnight figure and the
        # billed peak are on one scale and comparable.
        annual_max = self._annual_max_shape()
        if annual_max <= 0:
            return 0.0
        return float(shape[night].max() * (self.peak_kw / annual_max))

    def monthly_peaks(self) -> np.ndarray:
        return np.array([self.peak_day_window(m).max() for m in range(1, 13)])


@dataclass
class FixtureArchetype:
    """An archetype built directly from arrays. For tests and for pinning a
    known shape into a regression case without touching the network."""

    monthly_peak_kw: np.ndarray
    windows: np.ndarray  # shape (12, INTERVALS_PER_BILLED_DAY)
    source: Source = field(default="modeled")
    offpeak_max_kw: np.ndarray | None = None

    def __post_init__(self) -> None:
        self.monthly_peak_kw = np.asarray(self.monthly_peak_kw, dtype=float)
        self.windows = np.asarray(self.windows, dtype=float)
        if self.monthly_peak_kw.shape != (12,):
            raise ValueError("monthly_peak_kw must have shape (12,)")
        if self.windows.shape != (12, INTERVALS_PER_BILLED_DAY):
            raise ValueError(
                f"windows must have shape (12, {INTERVALS_PER_BILLED_DAY}), "
                f"got {self.windows.shape}"
            )
        if self.offpeak_max_kw is None:
            self.offpeak_max_kw = np.zeros(12, dtype=float)
        else:
            self.offpeak_max_kw = np.asarray(self.offpeak_max_kw, dtype=float)
        if self.offpeak_max_kw.shape != (12,):
            raise ValueError("offpeak_max_kw must have shape (12,)")

    def monthly_peaks(self) -> np.ndarray:
        return self.monthly_peak_kw

    def peak_day_window(self, month: int) -> np.ndarray:
        if not 1 <= month <= 12:
            raise ValueError(f"month must be 1-12, got {month}")
        return self.windows[month - 1]

    def offpeak_max(self, month: int) -> float:
        if not 1 <= month <= 12:
            raise ValueError(f"month must be 1-12, got {month}")
        return float(self.offpeak_max_kw[month - 1])

