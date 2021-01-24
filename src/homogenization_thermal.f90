!--------------------------------------------------------------------------------------------------
!> @author Martin Diehl, KU Leuven
!--------------------------------------------------------------------------------------------------
submodule(homogenization) homogenization_thermal

  use lattice

  type :: tDataContainer
    real(pReal), dimension(:), allocatable :: T, dot_T
  end type tDataContainer

  type(tDataContainer), dimension(:), allocatable :: current

  type :: tParameters
    character(len=pStringLen), allocatable, dimension(:) :: &
      output
  end type tParameters

  type(tparameters),             dimension(:), allocatable :: &
    param


contains

!--------------------------------------------------------------------------------------------------
!> @brief Allocate variables and set parameters.
!--------------------------------------------------------------------------------------------------
module subroutine thermal_init()

  class(tNode), pointer :: &
    configHomogenizations, &
    configHomogenization, &
    configHomogenizationThermal
  integer :: ho


  print'(/,a)',   ' <<<+-  homogenization_thermal init  -+>>>'


  configHomogenizations => config_material%get('homogenization')
  allocate(param(configHomogenizations%length))
  allocate(current(configHomogenizations%length))

  do ho = 1, configHomogenizations%length
    allocate(current(ho)%T(count(material_homogenizationAt2==ho)), source=thermal_initialT(ho))
    allocate(current(ho)%dot_T(count(material_homogenizationAt2==ho)), source=0.0_pReal)
    configHomogenization => configHomogenizations%get(ho)
    associate(prm => param(ho))
      if (configHomogenization%contains('thermal')) then
        configHomogenizationThermal => configHomogenization%get('thermal')
#if defined (__GFORTRAN__)
        prm%output = output_asStrings(configHomogenizationThermal)
#else
        prm%output = configHomogenizationThermal%get_asStrings('output',defaultVal=emptyStringArray)
#endif
      else
        prm%output = emptyStringArray
      endif
    end associate
  enddo

end subroutine thermal_init


!--------------------------------------------------------------------------------------------------
!> @brief Partition temperature onto the individual constituents.
!--------------------------------------------------------------------------------------------------
module subroutine thermal_partition(ce)

  integer,     intent(in) :: ce

  real(pReal) :: T, dot_T
  integer :: co


  T     = current(material_homogenizationAt2(ce))%T(material_homogenizationMemberAt2(ce))
  dot_T = current(material_homogenizationAt2(ce))%dot_T(material_homogenizationMemberAt2(ce))
  do co = 1, homogenization_Nconstituents(material_homogenizationAt2(ce))
    call constitutive_thermal_setField(T,dot_T,co,ce)
  enddo

end subroutine thermal_partition


!--------------------------------------------------------------------------------------------------
!> @brief Homogenize temperature rates
!--------------------------------------------------------------------------------------------------
module subroutine thermal_homogenize(ip,el)

  integer, intent(in) :: ip,el

  !call constitutive_thermal_getRate(homogenization_dot_T((el-1)*discretization_nIPs+ip), ip,el)

end subroutine thermal_homogenize


!--------------------------------------------------------------------------------------------------
!> @brief return homogenized thermal conductivity in reference configuration
!--------------------------------------------------------------------------------------------------
module function thermal_conduction_getConductivity(ip,el) result(K)

  integer, intent(in) :: &
    ip, &                                                                                           !< integration point number
    el                                                                                              !< element number
  real(pReal), dimension(3,3) :: K

  integer :: &
    co


  K = 0.0_pReal

  do co = 1, homogenization_Nconstituents(material_homogenizationAt(el))
    K = K + crystallite_push33ToRef(co,ip,el,lattice_K(:,:,material_phaseAt(co,el)))
  enddo

  K = K / real(homogenization_Nconstituents(material_homogenizationAt(el)),pReal)

end function thermal_conduction_getConductivity


!--------------------------------------------------------------------------------------------------
!> @brief returns homogenized specific heat capacity
!--------------------------------------------------------------------------------------------------
module function thermal_conduction_getSpecificHeat(ce) result(c_P)

  integer, intent(in) :: ce
  real(pReal) :: c_P

  integer :: co


  c_P = 0.0_pReal

  do co = 1, homogenization_Nconstituents(material_homogenizationAt2(ce))
    c_P = c_P + lattice_c_p(material_phaseAt2(co,ce))
  enddo

  c_P = c_P / real(homogenization_Nconstituents(material_homogenizationAt2(ce)),pReal)

end function thermal_conduction_getSpecificHeat


!--------------------------------------------------------------------------------------------------
!> @brief returns homogenized mass density
!--------------------------------------------------------------------------------------------------
module function thermal_conduction_getMassDensity(ce) result(rho)

  integer, intent(in) :: ce
  real(pReal) :: rho

  integer :: co


  rho = 0.0_pReal

  do co = 1, homogenization_Nconstituents(material_homogenizationAt2(ce))
    rho = rho + lattice_rho(material_phaseAt2(co,ce))
  enddo

  rho = rho / real(homogenization_Nconstituents(material_homogenizationAt2(ce)),pReal)

end function thermal_conduction_getMassDensity



!--------------------------------------------------------------------------------------------------
!> @brief Set thermal field and its rate (T and dot_T)
!--------------------------------------------------------------------------------------------------
module subroutine homogenization_thermal_setField(T,dot_T, ce)

  integer, intent(in) :: ce
  real(pReal),   intent(in) :: T, dot_T


  current(material_homogenizationAt2(ce))%T(material_homogenizationMemberAt2(ce)) = T
  current(material_homogenizationAt2(ce))%dot_T(material_homogenizationMemberAt2(ce)) = dot_T


end subroutine homogenization_thermal_setField


module function homogenization_thermal_T(ce) result(T)

  integer, intent(in) :: ce
  real(pReal) :: T

  T = current(material_homogenizationAt2(ce))%T(material_homogenizationMemberAt2(ce))

end function homogenization_thermal_T


end submodule homogenization_thermal
