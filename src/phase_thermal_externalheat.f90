!--------------------------------------------------------------------------------------------------
!> @author Martin Diehl, Max-Planck-Institut für Eisenforschung GmbH
!> @author Pratheek Shanthraj, Max-Planck-Institut für Eisenforschung GmbH
!> @author Philip Eisenlohr, Michigan State University
!> @brief material subroutine for variable heat source
!--------------------------------------------------------------------------------------------------
submodule(phase:thermal) externalheat


  integer,           dimension(:),   allocatable :: &
    source_thermal_externalheat_offset                                                           !< which source is my current thermal dissipation mechanism?

  type :: tParameters                                                                               !< container type for internal constitutive parameters
    real(pReal), dimension(:), allocatable :: &
      t_n, &
      f_T
    integer :: &
     nIntervals
  end type tParameters

  type(tParameters), dimension(:), allocatable  :: param                                            !< containers of constitutive parameters (len Ninstances)


contains


!--------------------------------------------------------------------------------------------------
!> @brief module initialization
!> @details reads in material parameters, allocates arrays, and does sanity checks
!--------------------------------------------------------------------------------------------------
module function externalheat_init(source_length) result(mySources)

  integer, intent(in)                  :: source_length
  logical, dimension(:,:), allocatable :: mySources

  class(tNode), pointer :: &
    phases, &
    phase, &
    sources, thermal, &
    src
  integer :: Ninstances,so,Nconstituents,ph

  print'(/,a)', ' <<<+-  phase:thermal:externalheat init  -+>>>'

  mySources = thermal_active('externalheat',source_length)

  Ninstances = count(mySources)
  print'(a,i2)', ' # instances: ',Ninstances; flush(IO_STDOUT)
  if(Ninstances == 0) return

  phases => config_material%get('phase')
  allocate(param(phases%length))
  allocate(source_thermal_externalheat_offset  (phases%length), source=0)

  do ph = 1, phases%length
    phase => phases%get(ph)
    if(count(mySources(:,ph)) == 0) cycle
    thermal => phase%get('thermal')
    sources => thermal%get('source')
    do so = 1, sources%length
      if(mySources(so,ph)) then
        source_thermal_externalheat_offset(ph) = so
        associate(prm  => param(ph))
          src => sources%get(so)

          prm%t_n = src%get_asFloats('t_n')
          prm%nIntervals = size(prm%t_n) - 1

          prm%f_T = src%get_asFloats('f_T',requiredSize = size(prm%t_n))

          Nconstituents = count(material_phaseAt2 == ph)
          call constitutive_allocateState(thermalState(ph)%p(so),Nconstituents,1,1,0)
        end associate
      endif
    enddo
  enddo

end function externalheat_init


!--------------------------------------------------------------------------------------------------
!> @brief rate of change of state
!> @details state only contains current time to linearly interpolate given heat powers
!--------------------------------------------------------------------------------------------------
module subroutine externalheat_dotState(ph, me)

  integer, intent(in) :: &
    ph, &
    me

  integer :: &
    so

  so = source_thermal_externalheat_offset(ph)

  thermalState(ph)%p(so)%dotState(1,me) = 1.0_pReal                                     ! state is current time

end subroutine externalheat_dotState


!--------------------------------------------------------------------------------------------------
!> @brief returns local heat generation rate
!--------------------------------------------------------------------------------------------------
module subroutine externalheat_getRate(TDot, ph, me)

  integer, intent(in) :: &
    ph, &
    me
  real(pReal),  intent(out) :: &
    TDot

  integer :: &
    so, interval
  real(pReal) :: &
    frac_time

  so = source_thermal_externalheat_offset(ph)

  associate(prm => param(ph))
    do interval = 1, prm%nIntervals                                                                   ! scan through all rate segments
      frac_time = (thermalState(ph)%p(so)%state(1,me) - prm%t_n(interval)) &
                / (prm%t_n(interval+1) - prm%t_n(interval))                                           ! fractional time within segment
      if (     (frac_time <  0.0_pReal .and. interval == 1) &
          .or. (frac_time >= 1.0_pReal .and. interval == prm%nIntervals) &
          .or. (frac_time >= 0.0_pReal .and. frac_time < 1.0_pReal) ) &
        TDot = prm%f_T(interval  ) * (1.0_pReal - frac_time) + &
               prm%f_T(interval+1) * frac_time                                                        ! interpolate heat rate between segment boundaries...
                                                                                                      ! ...or extrapolate if outside me bounds
    enddo
  end associate

end subroutine externalheat_getRate

end submodule externalheat
