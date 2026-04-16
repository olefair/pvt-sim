"""Soave-Redlich-Kwong equation of state implementation."""

from __future__ import annotations

import math
from typing import Callable, List, Literal, Optional, Union

import numpy as np
from numpy.typing import NDArray

from .base import CubicEOS
from ..core.constants import R
from ..core.errors import PhaseError
from ..models.component import Component

BIPInput = Union[
    NDArray[np.float64],
    Callable[[float], NDArray[np.float64]],
    "BIPProvider",
    None,
]


class SRKEOS(CubicEOS):
    """Soave-Redlich-Kwong cubic EOS.

    The SRK EOS equation:
        P = RT/(V-b) - a(T)/(V(V+b))

    In compressibility factor form:
        Z³ - Z² + (A-B-B²)Z - AB = 0
    """

    OMEGA_A = 0.42748
    OMEGA_B = 0.08664
    DELTA_1 = 1.0
    DELTA_2 = 0.0
    DELTA_DIFF = DELTA_1 - DELTA_2

    def __init__(self, components: List[Component]):
        super().__init__(components, name="Soave-Redlich-Kwong")
        self.u = 1.0
        self.w = 0.0

        self._calculate_critical_params()
        self._zero_kij = np.zeros((self.n_components, self.n_components))
        self._cached_temperature: Optional[float] = None
        self._cached_alpha: Optional[np.ndarray] = None
        self._cached_a_array: Optional[np.ndarray] = None
        self._cached_sqrt_a: Optional[np.ndarray] = None

    def _calculate_critical_params(self) -> None:
        """Pre-calculate temperature-independent SRK parameters."""
        self.a_c = np.zeros(self.n_components)
        self.b = np.zeros(self.n_components)
        self.m = np.zeros(self.n_components)

        for i, comp in enumerate(self.components):
            self.a_c[i] = (
                self.OMEGA_A * R.Pa_m3_per_mol_K ** 2 * comp.Tc ** 2 / comp.Pc
            )
            self.b[i] = self.OMEGA_B * R.Pa_m3_per_mol_K * comp.Tc / comp.Pc
            omega = comp.omega
            self.m[i] = 0.480 + 1.574 * omega - 0.176 * omega ** 2

    def alpha_function(self, temperature: float, component_idx: int) -> float:
        """Calculate the Soave alpha function."""
        comp = self.components[component_idx]
        Tr = temperature / comp.Tc
        sqrt_Tr = math.sqrt(Tr)
        m = self.m[component_idx]
        return (1.0 + m * (1.0 - sqrt_Tr)) ** 2

    def _get_temperature_params(self, temperature: float) -> tuple[np.ndarray, np.ndarray]:
        """Get cached or compute temperature-dependent parameters."""
        if self._cached_temperature != temperature:
            Tc_array = np.array([c.Tc for c in self.components])
            Tr = temperature / Tc_array
            sqrt_Tr = np.sqrt(Tr)
            self._cached_alpha = (1.0 + self.m * (1.0 - sqrt_Tr)) ** 2
            self._cached_a_array = self.a_c * self._cached_alpha
            self._cached_sqrt_a = np.sqrt(self._cached_a_array)
            self._cached_temperature = temperature

        return self._cached_a_array, self._cached_sqrt_a

    def _resolve_kij(
        self,
        temperature: float,
        binary_interaction: BIPInput,
    ) -> NDArray[np.float64]:
        """Resolve k_ij matrix from supported input forms."""
        if binary_interaction is None:
            return self._zero_kij
        if isinstance(binary_interaction, np.ndarray):
            return binary_interaction
        if callable(binary_interaction):
            return binary_interaction(temperature)
        if hasattr(binary_interaction, "get_kij_matrix"):
            return binary_interaction.get_kij_matrix(temperature)
        return self._zero_kij

    def calculate_params(
        self,
        temperature: float,
        composition: np.ndarray,
        binary_interaction: BIPInput = None,
    ) -> tuple[float, float, np.ndarray, np.ndarray]:
        """Calculate SRK mixture parameters."""
        composition = np.asarray(composition)
        a_array, sqrt_a = self._get_temperature_params(temperature)
        b_array = self.b
        b_mix = np.dot(composition, b_array)
        kij = self._resolve_kij(temperature, binary_interaction)

        sqrt_a_matrix = np.outer(sqrt_a, sqrt_a)
        a_ij_matrix = sqrt_a_matrix * (1.0 - kij)
        a_mix = np.dot(composition, np.dot(a_ij_matrix, composition))
        return a_mix, b_mix, a_array, b_array

    def fugacity_coefficient(
        self,
        pressure: float,
        temperature: float,
        composition: np.ndarray,
        phase: Literal["liquid", "vapor"] = "vapor",
        binary_interaction: BIPInput = None,
    ) -> np.ndarray:
        """Calculate SRK fugacity coefficients for all components."""
        from ..core.numerics.cubic_solver import solve_cubic_eos

        composition = np.asarray(composition)
        a_array, sqrt_a = self._get_temperature_params(temperature)
        b_array = self.b
        kij = self._resolve_kij(temperature, binary_interaction)

        b_mix = np.dot(composition, b_array)
        sqrt_a_matrix = np.outer(sqrt_a, sqrt_a)
        a_ij = sqrt_a_matrix * (1.0 - kij)
        a_mix = np.dot(composition, np.dot(a_ij, composition))

        RT = R.Pa_m3_per_mol_K * temperature
        A = a_mix * pressure / (RT * RT)
        B = b_mix * pressure / RT
        Z = solve_cubic_eos(A, B, root_type=phase, u=self.u, w=self.w)

        if Z <= B:
            raise PhaseError(
                f"Z={Z:.6f} <= B={B:.6f}: physically invalid SRK state.",
                phase=phase,
            )

        log_z_minus_b = math.log(Z - B)
        log_ratio = math.log((Z + self.DELTA_1 * B) / (Z + self.DELTA_2 * B))
        coeff = A / (B * self.DELTA_DIFF)

        sum_xj_aij = np.dot(a_ij, composition)
        bi_over_bmix = b_array / b_mix
        term1 = bi_over_bmix * (Z - 1.0)
        term2 = -log_z_minus_b
        bracket_term = 2.0 * sum_xj_aij / a_mix - bi_over_bmix
        term3 = -coeff * bracket_term * log_ratio

        return np.exp(term1 + term2 + term3)

    def _common_state(
        self,
        pressure: float,
        temperature: float,
        composition: np.ndarray,
        phase: Literal["liquid", "vapor"] = "vapor",
        binary_interaction: BIPInput = None,
    ) -> dict:
        """Intermediate quantities for ln(φ_i) and analytical derivatives (SRK).

        SRK compressibility cubic (u=1, w=0):
            Z³ - Z² + (A - B - B²) Z - A B = 0
        """
        from ..core.numerics.cubic_solver import solve_cubic_eos

        x = np.asarray(composition, dtype=np.float64)
        a_array, sqrt_a = self._get_temperature_params(temperature)
        b_array = self.b
        kij = self._resolve_kij(temperature, binary_interaction)

        b_mix = float(np.dot(x, b_array))
        sqrt_a_matrix = np.outer(sqrt_a, sqrt_a)
        a_ij = sqrt_a_matrix * (1.0 - kij)
        a_mix = float(np.dot(x, np.dot(a_ij, x)))

        RT = R.Pa_m3_per_mol_K * temperature
        A = a_mix * pressure / (RT * RT)
        B = b_mix * pressure / RT
        Z = float(solve_cubic_eos(A, B, root_type=phase, u=self.u, w=self.w))

        if Z <= B:
            raise PhaseError(
                f"Z={Z:.6f} <= B={B:.6f}: physically invalid SRK state.",
                phase=phase,
            )

        d1, d2 = self.DELTA_1, self.DELTA_2
        denom = Z + d2 * B
        if denom <= 0:
            raise PhaseError(
                f"Z + δ₂B = {denom:.6f} <= 0: invalid SRK state.",
                phase=phase,
            )

        log_Z_minus_B = math.log(Z - B)
        log_ratio = math.log((Z + d1 * B) / denom)
        coeff = A / (B * self.DELTA_DIFF) if B > 1e-30 else 0.0

        sum_xj_aij = np.dot(a_ij, x)
        bi_over_bmix = b_array / b_mix
        bracket = 2.0 * sum_xj_aij / a_mix - bi_over_bmix

        ln_phi = (
            bi_over_bmix * (Z - 1.0)
            - log_Z_minus_B
            - coeff * bracket * log_ratio
        )

        return {
            "Z": Z,
            "A": A,
            "B": B,
            "RT": RT,
            "a_mix": a_mix,
            "b_mix": b_mix,
            "a_ij": a_ij,
            "b_array": b_array,
            "sum_xj_aij": sum_xj_aij,
            "bi_over_bmix": bi_over_bmix,
            "bracket": bracket,
            "log_ratio": log_ratio,
            "log_Z_minus_B": log_Z_minus_B,
            "coeff": coeff,
            "ln_phi": ln_phi,
            "x": x,
            "P": pressure,
            "T": temperature,
        }

    def _dZ_dvar(self, Z: float, A: float, B: float, dA: float, dB: float) -> float:
        """∂Z/∂(var) via F(Z,A,B) = Z³ - Z² + (A-B-B²)Z - AB = 0."""
        dF_dZ = 3.0 * Z * Z - 2.0 * Z + (A - B - B * B)
        dF_dvar = (Z - B) * dA - (Z * (1.0 + 2.0 * B) + A) * dB
        if abs(dF_dZ) < 1e-30:
            return 0.0
        return -dF_dvar / dF_dZ

    def ln_fugacity_coefficient(
        self,
        pressure: float,
        temperature: float,
        composition: np.ndarray,
        phase: Literal["liquid", "vapor"] = "vapor",
        binary_interaction: BIPInput = None,
    ) -> np.ndarray:
        """ln(φ_i) without exp+log round-trip."""
        s = self._common_state(pressure, temperature, composition, phase, binary_interaction)
        return s["ln_phi"]

    def d_ln_phi_dP(
        self,
        pressure: float,
        temperature: float,
        composition: np.ndarray,
        phase: Literal["liquid", "vapor"] = "vapor",
        binary_interaction: BIPInput = None,
    ) -> np.ndarray:
        """Analytical ∂ln(φ_i)/∂P at constant T, x for SRK."""
        s = self._common_state(pressure, temperature, composition, phase, binary_interaction)
        Z, A, B, P = s["Z"], s["A"], s["B"], s["P"]
        bi_bm = s["bi_over_bmix"]
        bracket = s["bracket"]
        log_ratio = s["log_ratio"]
        coeff = s["coeff"]

        dA_dP = A / P
        dB_dP = B / P
        dZ_dP = self._dZ_dvar(Z, A, B, dA_dP, dB_dP)

        d1, d2 = self.DELTA_1, self.DELTA_2
        num = Z + d1 * B
        den = Z + d2 * B

        d_term1 = bi_bm * dZ_dP
        d_term2 = -(dZ_dP - dB_dP) / (Z - B)

        if B > 1e-30:
            d_log_ratio = (dZ_dP + d1 * dB_dP) / num - (dZ_dP + d2 * dB_dP) / den
            # A/B is independent of P at fixed T,x → d(coeff)/dP = 0
            d_coeff_dP = 0.0
            d_bracket_dP = np.zeros_like(bracket)
            d_term3 = -(
                d_coeff_dP * bracket * log_ratio
                + coeff * (d_bracket_dP * log_ratio + bracket * d_log_ratio)
            )
        else:
            d_term3 = np.zeros(self.n_components)

        return d_term1 + d_term2 + d_term3

    def d_ln_phi_dn(
        self,
        pressure: float,
        temperature: float,
        composition: np.ndarray,
        phase: Literal["liquid", "vapor"] = "vapor",
        binary_interaction: BIPInput = None,
    ) -> np.ndarray:
        """Analytical ∂ln(φ_i)/∂n_j (n_c × n_c) for SRK.

        Same mole-number identity as PR: J = dlnphi_dx - (dlnphi_dx @ x)[:, None].
        """
        s = self._common_state(pressure, temperature, composition, phase, binary_interaction)
        Z, A, B = s["Z"], s["A"], s["B"]
        a_mix, b_mix = s["a_mix"], s["b_mix"]
        a_ij, b_arr = s["a_ij"], s["b_array"]
        bi_bm = s["bi_over_bmix"]
        bracket = s["bracket"]
        log_ratio = s["log_ratio"]
        coeff = s["coeff"]
        x = s["x"]
        sum_xk_aki = s["sum_xj_aij"]

        nc = self.n_components
        d1, d2 = self.DELTA_1, self.DELTA_2
        num = Z + d1 * B
        den = Z + d2 * B

        dlnphi_dx = np.zeros((nc, nc))

        for j in range(nc):
            da_mix_dxj = 2.0 * sum_xk_aki[j]
            db_mix_dxj = b_arr[j]

            dA_dxj = A * da_mix_dxj / a_mix if a_mix > 1e-30 else 0.0
            dB_dxj = B * db_mix_dxj / b_mix if b_mix > 1e-30 else 0.0

            dZ_dxj = self._dZ_dvar(Z, A, B, dA_dxj, dB_dxj)

            d_bi_bm_dxj = -bi_bm * db_mix_dxj / b_mix if b_mix > 1e-30 else 0.0

            d_term1 = d_bi_bm_dxj * (Z - 1.0) + bi_bm * dZ_dxj
            d_term2 = -(dZ_dxj - dB_dxj) / (Z - B)

            if B > 1e-30:
                d_sum_xk_aik_dxj = a_ij[:, j]
                d_bracket_dxj = (
                    2.0
                    * (d_sum_xk_aik_dxj * a_mix - sum_xk_aki * da_mix_dxj)
                    / (a_mix * a_mix)
                    - d_bi_bm_dxj
                )
                d_log_ratio_dxj = (dZ_dxj + d1 * dB_dxj) / num - (dZ_dxj + d2 * dB_dxj) / den
                d_coeff_dxj = (dA_dxj * B - A * dB_dxj) / (B * B)

                d_term3 = -(
                    d_coeff_dxj * bracket * log_ratio
                    + coeff * d_bracket_dxj * log_ratio
                    + coeff * bracket * d_log_ratio_dxj
                )
            else:
                d_term3 = np.zeros(nc)

            dlnphi_dx[:, j] = d_term1 + d_term2 + d_term3

        correction = dlnphi_dx @ x
        return dlnphi_dx - correction[:, np.newaxis]

    def __repr__(self) -> str:
        return f"SRKEOS(n_components={self.n_components})"
