! Legacy Fortran kernels for the physics simulator.
!
! The Aero semantic mapper extracts the module-level parameter (uast_global),
! the functions (uast_function), and recognises `bind(c)` interfaces as
! `fortran_c_abi` FFI bindings into the C/Rust core.

module legacy_kernels
  implicit none
  real(8), parameter :: GRAVITY = 9.80665d0
contains

  function kinetic_energy(mass, velocity) bind(c, name="kinetic_energy")
    real(8), value :: mass, velocity
    real(8) :: kinetic_energy
    kinetic_energy = 0.5d0 * mass * velocity * velocity
  end function kinetic_energy

  function potential_energy(mass, height) bind(c, name="potential_energy")
    real(8), value :: mass, height
    real(8) :: potential_energy
    potential_energy = mass * GRAVITY * height
  end function potential_energy

end module legacy_kernels
