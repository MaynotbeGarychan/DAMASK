#!/usr/bin/python
# -*- coding: UTF-8 no BOM -*-

import threading,time,os,subprocess,shlex,string
import numpy as np
from scipy.optimize import curve_fit
from scipy.linalg import svd
from optparse import OptionParser
import damask

scriptID = '$Id$'
scriptName = scriptID.split()[1]

def execute(cmd,dir='./'):
      
  initialPath=os.getcwd()
  os.chdir(dir)
  out = ''
  line = True
  process = subprocess.Popen(shlex.split(cmd),stdout=subprocess.PIPE,stderr = subprocess.STDOUT)
  while line:
    line = process.stdout.readline()
    out += line
  os.chdir(initialPath)


def Hill48(x, F,G,H,L,M,N):
  a = F*(x[4]-x[8])**2.0 + G*(x[8]-x[0])**2.0 + H*(x[0]-x[4])**2.0 + \
         2.0*L*x[1]**2.0 + 2.0*M*x[2]**2.0 + 2.0*N*x[5]**2.0 -1.0
  return a.ravel()


def vonMises(x, S_y):
  sv=np.zeros(0,'d')
  for i in xrange(np.shape(x)[1]):
    U, l, Vh = svd(np.array(x[:,i]).reshape(3,3))
    sv = np.append(sv,l)
  sv = sv.reshape(np.shape(x)[1],3)
  ooo = (sv[:,2]-sv[:,1])**2+(sv[:,1]-sv[:,0])**2+(sv[:,0]-sv[:,2])**2-2*S_y**2
  return ooo.ravel()

fittingCriteria = {
                   'vonMises':{'fit':np.ones(1,'d'),'err':np.inf},
                   'hill48'  :{'fit':np.ones(6,'d'),'err':np.inf},
                   'worst'   :{'err':np.inf},
                   'best'    :{'err':np.inf}
                   }
thresholdParameter = ['totalshear','equivalentStrain']

#---------------------------------------------------------------------------------------------------
class Loadcase():
#---------------------------------------------------------------------------------------------------
  '''
     Class for generating load cases for the spectral solver
  '''

# ------------------------------------------------------------------
  def __init__(self,finalStrain,incs,time):
    print('using the random load case generator')
    self.finalStrain = finalStrain
    self.incs = incs
    self.time = time

  def getLoadcase(self,N=0):
    defgrad=['*']*9
    stress =[0]*9
    values=(np.random.random_sample(9)-.5)*self.finalStrain*2

    main=np.array([0,4,8])
    np.random.shuffle(main)
    for i in main[:2]:                                                                              # fill 2 out of 3 main entries
      defgrad[i]=1.+values[i]
      stress[i]='*'
    for off in [[1,3,0],[2,6,0],[5,7,0]]:                                                           # fill 3 off-diagonal pairs of defgrad (1 or 2 entries)
      off=np.array(off)
      np.random.shuffle(off)
      for i in off[0:2]:
        if i != 0: 
          defgrad[i]=values[i]
          stress[i]='*'

    return 'f '+' '.join(str(c) for c in defgrad)+\
          ' p '+' '.join(str(c) for c in stress)+\
          ' incs %s'%self.incs+\
          ' time %s'%self.time

#---------------------------------------------------------------------------------------------------
class Criterion(object):
#---------------------------------------------------------------------------------------------------
  '''
     Fitting to certain criterion
  '''
  def __init__(self,name='worst'):
    self.name = name
    self.results = fittingCriteria
    
    if self.name.lower() not in map(str.lower, self.results.keys()):
      raise Exception('no suitable fitting criterion selected')
    else:
      print('fitting to the %s criterion'%name)

  def fit(self,stress):
    try:  
      popt, pcov = curve_fit(vonMises, stress, np.zeros(np.shape(stress)[1]))
      print 'Mises', popt
    except Exception as detail:
      print detail
      pass
    try:
      popt, pcov = curve_fit(Hill48, stress, np.zeros(np.shape(stress)[1]))
      print 'Hill48', popt
    except Exception as detail:
      print detail
      pass


#---------------------------------------------------------------------------------------------------
class myThread (threading.Thread):
#---------------------------------------------------------------------------------------------------
  '''
     Runner class
  '''
  def __init__(self, threadID):
    threading.Thread.__init__(self)
    self.threadID = threadID
  def run(self):
    s.acquire()
    conv=converged()
    s.release()
    while not conv:
      doSim(4.,self.name)
      s.acquire()
      conv=converged()
      s.release()

def doSim(delay,thread):
  
  s.acquire()
  me=getLoadcase()
  if not os.path.isfile('%s.load'%me):
    print('generating loadcase for sim %s from %s'%(me,thread))
    f=open('%s.load'%me,'w')
    f.write(myLoad.getLoadcase(me))
    f.close()
    s.release()
  else: s.release()
  
  s.acquire()
  if not os.path.isfile('%s_%i.spectralOut'%(options.geometry,me)):
    print('starting simulation %s from %s'%(me,thread))
    s.release()
    execute('DAMASK_spectral -g %s -l %i'%(options.geometry,me))
  else: s.release()
   
  s.acquire()
  if not os.path.isfile('./postProc/%s_%i.txt'%(options.geometry,me)):
    print('starting post processing for sim %i from %s'%(me,thread))
    s.release()
    try:
      execute('postResults --cr f,p --co totalshear %s_%i.spectralOut'%(options.geometry,me))
    except:
      execute('postResults --cr f,p %s_%i.spectralOut'%(options.geometry,me))
    execute('addCauchy ./postProc/%s_%i.txt'%(options.geometry,me))
    execute('addStrainTensors -l -v ./postProc/%s_%i.txt'%(options.geometry,me))
    execute('addMises -s Cauchy -e ln(V) ./postProc/%s_%i.txt'%(options.geometry,me))
  else: s.release()

  s.acquire()
  print('reading values for sim %i from %s'%(me,thread))
  s.release()

  refFile = open('./postProc/%s_%i.txt'%(options.geometry,me))
  table = damask.ASCIItable(refFile)
  table.head_read()
  if options.fitting =='equivalentStrain':
    thresholdKey = 'Mises(ln(V))'
  elif options.fitting =='totalshear':
    thresholdKey = 'totalshear'
  s.acquire()
  for l in [thresholdKey,'1_Cauchy']:
    if l not in table.labels: print '%s not found'%l
  s.release()
  table.data_readArray(['%i_Cauchy'%(i+1) for i in xrange(9)]+[thresholdKey])

  line = 0
  lines = np.shape(table.data)[0]
  yieldStress=[None for i in xrange(int(options.yieldValue[2]))]
  for i,j in enumerate(np.linspace(options.yieldValue[0],options.yieldValue[1],options.yieldValue[2])):
    while line < lines:
      if table.data[line,9]>= j:
        upper,lower = table.data[line,9],table.data[line-1,9]                                          # weights for linear interpolation
        yieldStress[i] = table.data[line,  0:9] * (upper-j)/(upper-lower) \
                       + table.data[line-1,0:9] * (j-lower)/(upper-lower)                              # linear interpolation of stress values
        break
      else:
        line+=1
  
  s.acquire()
  global stressAll
  print('starting fitting for sim %i from %s'%(me,thread))
  try:
    for i in xrange(int(options.yieldValue[2])):
      stressAll[i]=np.append(yieldStress[i]/10.e8,stressAll[i])
      myFit.fit(stressAll[i].reshape(len(stressAll[i])//9,9).transpose())
  except Exception:
    print('could not fit for sim %i from %s'%(me,thread))
    s.release()
    return
  s.release()

def getLoadcase():
  global N_simulations
  N_simulations+=1
  return N_simulations

def converged():
  global N_simulations
  if N_simulations < options.max:
    return False
  else:
    return True

# --------------------------------------------------------------------
#                                MAIN
# --------------------------------------------------------------------

parser = OptionParser(option_class=damask.extendableOption, usage='%prog options [file[s]]', description = """
Performs calculations with various loads on given geometry file and fits yield surface.

""", version=string.replace(scriptID,'\n','\\n')
)

parser.add_option('-l','--load' ,    dest='load', type='float', nargs=3,
                                     help='load: final strain; increments; time %default', metavar='float int float')
parser.add_option('-g','--geometry', dest='geometry', type='string',
                                     help='name of the geometry file [%default]', metavar='string')
parser.add_option('--criterion',     dest='criterion', choices=fittingCriteria.keys(),
                                     help='criterion for stopping simulations [%default]', metavar='string')
parser.add_option('--fitting',       dest='fitting', choices=thresholdParameter,
                                     help='yield criterion [%default]', metavar='string')
parser.add_option('--yieldvalue',    dest='yieldValue', type='float', nargs=3,
                                     help='yield points: start; end; count %default', metavar='float float int')
parser.add_option('--min',           dest='min', type='int',
                                     help='minimum number of simulations [%default]', metavar='int')
parser.add_option('--max',           dest='max', type='int',
                                     help='maximum number of iterations [%default]',  metavar='int')
parser.add_option('--threads',       dest='threads', type='int',
                                     help='number of parallel executions [%default]',  metavar='int')
parser.set_defaults(min        = 12)
parser.set_defaults(max        = 30)
parser.set_defaults(threads    = 4)
parser.set_defaults(yieldValue = (0.002,0.002,1))
parser.set_defaults(load       = (0.010,100,100.0))
parser.set_defaults(criterion  = 'worst')
parser.set_defaults(fitting    = 'totalshear')
parser.set_defaults(geometry   = '20grains16x16x16')

options = parser.parse_args()[0]

if not os.path.isfile(options.geometry+'.geom'):
  parser.error('geometry file %s.geom not found'%options.geometry)
if not os.path.isfile('material.config'):
  parser.error('material.config file not found')
if options.threads<1:
  parser.error('invalid number of threads %i'%options.threads)
if options.min<0:
  parser.error('invalid minimum number of simulations %i'%options.min)
if options.max<options.min:
  parser.error('invalid maximum number of simulations (below minimum)')
if options.yieldValue[0]>options.yieldValue[1]:
  parser.error('invalid yield start (below yield end)')
if options.yieldValue[2] != int(options.yieldValue[2]):
  parser.error('count must be an integer')
if not os.path.isfile('numerics.config'):
  print('numerics.config file not found')

if not os.path.isfile('material.config'):
  print('material.config file not found')

N_simulations=0
s=threading.Semaphore(1)

stressAll=[np.zeros(0,'d').reshape(0,0) for i in xrange(int(options.yieldValue[2]))]
myLoad = Loadcase(options.load[0],options.load[1],options.load[2])
myFit = Criterion(options.criterion)

threads=[]

for i in range(options.threads):
  threads.append(myThread(i))
  threads[i].start()

for i in range(options.threads):
  threads[i].join()

print 'finished fitting to yield criteria'
