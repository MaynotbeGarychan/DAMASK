!--------------------------------------------------------------------------------------------------
!> @author Franz Roters, Max-Planck-Institut für Eisenforschung GmbH
!> @author Philip Eisenlohr, Max-Planck-Institut für Eisenforschung GmbH
!> @author Martin Diehl, Max-Planck-Institut für Eisenforschung GmbH
!> @brief material subroutine for isotropic plasticity
!> @details Isotropic Plasticity which resembles the phenopowerlaw plasticity without
!! resolving the stress on the slip systems. Will give the response of phenopowerlaw for an
!! untextured polycrystal
!--------------------------------------------------------------------------------------------------
submodule(constitutive) plastic_isotropic
  
  enum, bind(c)
    enumerator :: &
      undefined_ID, &
      xi_ID, &
      dot_gamma_ID
  end enum
 
  type :: tParameters
    real(pReal) :: &
      M, &                                                                                          !< Taylor factor
      xi_0, &                                                                                       !< initial critical stress
      dot_gamma_0, &                                                                                !< reference strain rate
      n, &                                                                                          !< stress exponent
      h0, &
      h_ln, &
      xi_inf, &                                                                                     !< maximum critical stress
      a, &
      c_1, &
      c_4, &
      c_3, &
      c_2, &
      aTol_xi, &
      aTol_gamma
    integer :: &
      of_debug = 0
    integer(kind(undefined_ID)), allocatable, dimension(:) :: &
      outputID
    logical :: &
      dilatation
  end type tParameters
 
  type :: tIsotropicState
    real(pReal), pointer, dimension(:) :: &
      xi, &
      gamma
  end type tIsotropicState

!--------------------------------------------------------------------------------------------------
! containers for parameters and state
 type(tParameters),     allocatable, dimension(:) :: param
 type(tIsotropicState), allocatable, dimension(:) :: &
   dotState, &
   state

contains

!--------------------------------------------------------------------------------------------------
!> @brief module initialization
!> @details reads in material parameters, allocates arrays, and does sanity checks
!--------------------------------------------------------------------------------------------------
module subroutine plastic_isotropic_init

  integer :: &
    Ninstance, &
    p, i, &
    NipcMyPhase, &
    sizeState, sizeDotState
 
  integer(kind(undefined_ID)) :: &
    outputID
 
  character(len=pStringLen) :: &
    extmsg = ''
  character(len=pStringLen), dimension(:), allocatable :: &
    outputs
 
  write(6,'(/,a)')   ' <<<+-  plastic_'//PLASTICITY_ISOTROPIC_label//' init  -+>>>'
 
  write(6,'(/,a)')   ' Maiti and Eisenlohr, Scripta Materialia 145:37–40, 2018'
  write(6,'(a)')     ' https://doi.org/10.1016/j.scriptamat.2017.09.047'
 
  Ninstance = count(phase_plasticity == PLASTICITY_ISOTROPIC_ID)
  if (iand(debug_level(debug_constitutive),debug_levelBasic) /= 0) &
    write(6,'(a16,1x,i5,/)') '# instances:',Ninstance
 
  allocate(param(Ninstance))
  allocate(state(Ninstance))
  allocate(dotState(Ninstance))
 
  do p = 1, size(phase_plasticity)
    if (phase_plasticity(p) /= PLASTICITY_ISOTROPIC_ID) cycle
    associate(prm => param(phase_plasticityInstance(p)), &
              dot => dotState(phase_plasticityInstance(p)), &
              stt => state(phase_plasticityInstance(p)), &
              config => config_phase(p))
 
#ifdef DEBUG
    if  (p==material_phaseAt(debug_g,debug_e)) &
      prm%of_debug = material_phasememberAt(debug_g,debug_i,debug_e)
#endif
 
    prm%xi_0            = config%getFloat('tau0')
    prm%xi_inf          = config%getFloat('tausat')
    prm%dot_gamma_0     = config%getFloat('gdot0')
    prm%n               = config%getFloat('n')
    prm%h0              = config%getFloat('h0')
    prm%M               = config%getFloat('m')
    prm%h_ln            = config%getFloat('h0_slopelnrate', defaultVal=0.0_pReal)
    prm%c_1             = config%getFloat('tausat_sinhfita',defaultVal=0.0_pReal)
    prm%c_4             = config%getFloat('tausat_sinhfitb',defaultVal=0.0_pReal)
    prm%c_3             = config%getFloat('tausat_sinhfitc',defaultVal=0.0_pReal)
    prm%c_2             = config%getFloat('tausat_sinhfitd',defaultVal=0.0_pReal)
    prm%a               = config%getFloat('a')
    prm%aTol_xi         = config%getFloat('atol_flowstress',defaultVal=1.0_pReal)
    prm%aTol_gamma      = config%getFloat('atol_shear',     defaultVal=1.0e-6_pReal)
 
    prm%dilatation      = config%keyExists('/dilatation/')
 
!--------------------------------------------------------------------------------------------------
!  sanity checks
    extmsg = ''
    if (prm%aTol_gamma     <= 0.0_pReal) extmsg = trim(extmsg)//' aTol_gamma'
    if (prm%xi_0           <  0.0_pReal) extmsg = trim(extmsg)//' xi_0'
    if (prm%dot_gamma_0    <= 0.0_pReal) extmsg = trim(extmsg)//' dot_gamma_0'
    if (prm%n              <= 0.0_pReal) extmsg = trim(extmsg)//' n'
    if (prm%a              <= 0.0_pReal) extmsg = trim(extmsg)//' a'
    if (prm%M              <= 0.0_pReal) extmsg = trim(extmsg)//' m'
    if (prm%aTol_xi        <= 0.0_pReal) extmsg = trim(extmsg)//' atol_xi'
    if (prm%aTol_gamma     <= 0.0_pReal) extmsg = trim(extmsg)//' atol_shear'
 
!--------------------------------------------------------------------------------------------------
!  exit if any parameter is out of range
    if (extmsg /= '') &
      call IO_error(211,ext_msg=trim(extmsg)//'('//PLASTICITY_ISOTROPIC_label//')')
 
!--------------------------------------------------------------------------------------------------
!  output pararameters
    outputs = config%getStrings('(output)',defaultVal=emptyStringArray)
    allocate(prm%outputID(0))
    do i=1, size(outputs)
      outputID = undefined_ID
      select case(outputs(i))
 
        case ('flowstress')
          outputID = xi_ID
        case ('strainrate')
          outputID = dot_gamma_ID
 
      end select
 
      if (outputID /= undefined_ID) then
        prm%outputID = [prm%outputID, outputID]
     endif
 
    enddo
 
!--------------------------------------------------------------------------------------------------
! allocate state arrays
    NipcMyPhase = count(material_phaseAt == p) * discretization_nIP
    sizeDotState = size(['xi               ','accumulated_shear'])
    sizeState = sizeDotState
 
    call material_allocatePlasticState(p,NipcMyPhase,sizeState,sizeDotState,0)
 
!--------------------------------------------------------------------------------------------------
! locally defined state aliases and initialization of state0 and aTolState
    stt%xi  => plasticState(p)%state   (1,:)
    stt%xi  = prm%xi_0
    dot%xi  => plasticState(p)%dotState(1,:)
    plasticState(p)%aTolState(1) = prm%aTol_xi
 
    stt%gamma  => plasticState(p)%state   (2,:)
    dot%gamma  => plasticState(p)%dotState(2,:)
    plasticState(p)%aTolState(2) = prm%aTol_gamma
    ! global alias
    plasticState(p)%slipRate        => plasticState(p)%dotState(2:2,:)
 
    plasticState(p)%state0 = plasticState(p)%state                                                  ! ToDo: this could be done centrally
 
    end associate
 
  enddo

end subroutine plastic_isotropic_init


!--------------------------------------------------------------------------------------------------
!> @brief calculates plastic velocity gradient and its tangent
!--------------------------------------------------------------------------------------------------
module subroutine plastic_isotropic_LpAndItsTangent(Lp,dLp_dMp,Mp,instance,of)
 
  real(pReal), dimension(3,3),     intent(out) :: &
    Lp                                                                                              !< plastic velocity gradient
  real(pReal), dimension(3,3,3,3), intent(out) :: &
    dLp_dMp                                                                                         !< derivative of Lp with respect to the Mandel stress
 
  real(pReal), dimension(3,3), intent(in) :: &
    Mp                                                                                              !< Mandel stress
  integer,                     intent(in) :: &
    instance, &
    of
 
  real(pReal), dimension(3,3) :: &
    Mp_dev                                                                                          !< deviatoric part of the Mandel stress
  real(pReal) :: &
    dot_gamma, &                                                                                    !< strainrate
    norm_Mp_dev, &                                                                                  !< norm of the deviatoric part of the Mandel stress
    squarenorm_Mp_dev                                                                               !< square of the norm of the deviatoric part of the Mandel stress
  integer :: &
    k, l, m, n
 
  associate(prm => param(instance), stt => state(instance))
 
  Mp_dev = math_deviatoric33(Mp)
  squarenorm_Mp_dev = math_mul33xx33(Mp_dev,Mp_dev)
  norm_Mp_dev = sqrt(squarenorm_Mp_dev)
 
  if (norm_Mp_dev > 0.0_pReal) then
    dot_gamma = prm%dot_gamma_0 * (sqrt(1.5_pReal) * norm_Mp_dev/(prm%M*stt%xi(of))) **prm%n
 
    Lp = dot_gamma/prm%M * Mp_dev/norm_Mp_dev
#ifdef DEBUG
    if (iand(debug_level(debug_constitutive), debug_levelExtensive) /= 0 &
        .and. (of == prm%of_debug .or. .not. iand(debug_level(debug_constitutive),debug_levelSelective) /= 0)) then
      write(6,'(/,a,/,3(12x,3(f12.4,1x)/))') '<< CONST isotropic >> Tstar (dev) / MPa', &
                                       transpose(Mp_dev)*1.0e-6_pReal
      write(6,'(/,a,/,f12.5)') '<< CONST isotropic >> norm Tstar / MPa', norm_Mp_dev*1.0e-6_pReal
      write(6,'(/,a,/,f12.5)') '<< CONST isotropic >> gdot', dot_gamma
    end if
#endif
    forall (k=1:3,l=1:3,m=1:3,n=1:3) &
      dLp_dMp(k,l,m,n) = (prm%n-1.0_pReal) * Mp_dev(k,l)*Mp_dev(m,n) / squarenorm_Mp_dev
    forall (k=1:3,l=1:3) &
      dLp_dMp(k,l,k,l) = dLp_dMp(k,l,k,l) + 1.0_pReal
    forall (k=1:3,m=1:3) &
      dLp_dMp(k,k,m,m) = dLp_dMp(k,k,m,m) - 1.0_pReal/3.0_pReal
    dLp_dMp = dot_gamma / prm%M * dLp_dMp / norm_Mp_dev
  else
    Lp = 0.0_pReal
    dLp_dMp = 0.0_pReal
  end if
 
  end associate

end subroutine plastic_isotropic_LpAndItsTangent


!--------------------------------------------------------------------------------------------------
!> @brief calculates plastic velocity gradient and its tangent
!--------------------------------------------------------------------------------------------------
module subroutine plastic_isotropic_LiAndItsTangent(Li,dLi_dMi,Mi,instance,of)
 
  real(pReal), dimension(3,3), intent(out) :: &
    Li                                                                                              !< inleastic velocity gradient
  real(pReal), dimension(3,3,3,3), intent(out)  :: &
    dLi_dMi                                                                                         !< derivative of Li with respect to Mandel stress
 
  real(pReal), dimension(3,3),   intent(in) :: &
    Mi                                                                                              !< Mandel stress 
  integer,                       intent(in) :: &
    instance, &
    of
 
  real(pReal) :: &
    tr                                                                                              !< trace of spherical part of Mandel stress (= 3 x pressure)
  integer :: &
    k, l, m, n
 
  associate(prm => param(instance), stt => state(instance))
 
  tr=math_trace33(math_spherical33(Mi))

  if (prm%dilatation .and. abs(tr) > 0.0_pReal) then                                                 ! no stress or J2 plasticity --> Li and its derivative are zero
    Li = math_I3 &
       * prm%dot_gamma_0/prm%M * (3.0_pReal*prm%M*stt%xi(of))**(-prm%n) &
       * tr * abs(tr)**(prm%n-1.0_pReal)
 
#ifdef DEBUG
    if (iand(debug_level(debug_constitutive), debug_levelExtensive) /= 0 &
        .and. (of == prm%of_debug .or. .not. iand(debug_level(debug_constitutive),debug_levelSelective) /= 0)) then
      write(6,'(/,a,/,f12.5)') '<< CONST isotropic >> pressure / MPa', tr/3.0_pReal*1.0e-6_pReal
      write(6,'(/,a,/,f12.5)') '<< CONST isotropic >> gdot', prm%dot_gamma_0 * (3.0_pReal*prm%M*stt%xi(of))**(-prm%n) &
                                                           * tr * abs(tr)**(prm%n-1.0_pReal)
    end if
#endif

    forall (k=1:3,l=1:3,m=1:3,n=1:3) &
      dLi_dMi(k,l,m,n) = prm%n / tr * Li(k,l) * math_I3(m,n)

  else
    Li      = 0.0_pReal
    dLi_dMi = 0.0_pReal
  endif
 
  end associate

 end subroutine plastic_isotropic_LiAndItsTangent


!--------------------------------------------------------------------------------------------------
!> @brief calculates the rate of change of microstructure
!--------------------------------------------------------------------------------------------------
module subroutine plastic_isotropic_dotState(Mp,instance,of)
 
  real(pReal), dimension(3,3),  intent(in) :: &
    Mp                                                                                              !< Mandel stress
  integer,                      intent(in) :: &
    instance, &
    of
 
  real(pReal) :: &
    dot_gamma, &                                                                                    !< strainrate
    xi_inf_star, &                                                                                  !< saturation xi
    norm_Mp                                                                                         !< norm of the (deviatoric) Mandel stress
 
  associate(prm => param(instance), stt => state(instance), dot => dotState(instance))
 
  if (prm%dilatation) then
    norm_Mp = sqrt(math_mul33xx33(Mp,Mp))
  else
    norm_Mp = sqrt(math_mul33xx33(math_deviatoric33(Mp),math_deviatoric33(Mp)))
  endif
 
  dot_gamma = prm%dot_gamma_0 * (sqrt(1.5_pReal) * norm_Mp /(prm%M*stt%xi(of))) **prm%n
 
  if (dot_gamma > 1e-12_pReal) then
    if (dEq0(prm%c_1)) then
      xi_inf_star = prm%xi_inf
    else
      xi_inf_star = prm%xi_inf &
                  + asinh( (dot_gamma / prm%c_1)**(1.0_pReal / prm%c_2))**(1.0_pReal / prm%c_3) &
                  / prm%c_4 * (dot_gamma / prm%dot_gamma_0)**(1.0_pReal / prm%n)
    endif
    dot%xi(of) = dot_gamma &
               * ( prm%h0 + prm%h_ln * log(dot_gamma) ) &
               * abs( 1.0_pReal - stt%xi(of)/xi_inf_star )**prm%a &
               * sign(1.0_pReal, 1.0_pReal - stt%xi(of)/xi_inf_star)
  else
    dot%xi(of) = 0.0_pReal
  endif
 
  dot%gamma(of) = dot_gamma                                                                         ! ToDo: not really used
 
  end associate

end subroutine plastic_isotropic_dotState


!--------------------------------------------------------------------------------------------------
!> @brief writes results to HDF5 output file
!--------------------------------------------------------------------------------------------------
module subroutine plastic_isotropic_results(instance,group)

  integer, intent(in) :: instance
  character(len=*), intent(in) :: group
  
  integer :: o

  associate(prm => param(instance), stt => state(instance))
  outputsLoop: do o = 1,size(prm%outputID)
    select case(prm%outputID(o))
      case (xi_ID)
        call results_writeDataset(group,stt%xi,'xi','resistance against plastic flow','Pa')
    end select
  enddo outputsLoop
  end associate

end subroutine plastic_isotropic_results


end submodule plastic_isotropic
