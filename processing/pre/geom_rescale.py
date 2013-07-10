#!/usr/bin/env python
# -*- coding: UTF-8 no BOM -*-

import os,sys,string,re,math,numpy
import damask
from optparse import OptionParser, OptionGroup, Option, SUPPRESS_HELP

scriptID = '$Id$'
scriptName = scriptID.split()[1]

#--------------------------------------------------------------------------------------------------
class extendedOption(Option):
#--------------------------------------------------------------------------------------------------
# used for definition of new option parser action 'extend', which enables to take multiple option arguments
# taken from online tutorial http://docs.python.org/library/optparse.html
    
    ACTIONS = Option.ACTIONS + ("extend",)
    STORE_ACTIONS = Option.STORE_ACTIONS + ("extend",)
    TYPED_ACTIONS = Option.TYPED_ACTIONS + ("extend",)
    ALWAYS_TYPED_ACTIONS = Option.ALWAYS_TYPED_ACTIONS + ("extend",)

    def take_action(self, action, dest, opt, value, values, parser):
        if action == "extend":
            lvalue = value.split(",")
            values.ensure_value(dest, []).extend(lvalue)
        else:
            Option.take_action(self, action, dest, opt, value, values, parser)


#--------------------------------------------------------------------------------------------------
#                                MAIN
#--------------------------------------------------------------------------------------------------
synonyms = {
        'grid':   ['resolution'],
        'size':   ['dimension'],
          }
identifiers = {
        'grid':   ['a','b','c'],
        'size':   ['x','y','z'],
        'origin': ['x','y','z'],
          }
mappings = {
        'grid':            lambda x: int(x),
        'size':            lambda x: float(x),
        'origin':          lambda x: float(x),
        'homogenization':  lambda x: int(x),
        'microstructures': lambda x: int(x),
          }

parser = OptionParser(option_class=extendedOption, usage='%prog options [file[s]]', description = """
Scales a geometry description independently in x, y, and z direction in terms of grid and/or size.
Either absolute values or relative factors (like "0.25x") can be used.
""" + string.replace(scriptID,'\n','\\n')
)

parser.add_option('-g', '--grid', dest='grid', type='string', nargs = 3, \
                  help='a,b,c grid of hexahedral box [unchanged]')
parser.add_option('-s', '--size', dest='size', type='string', nargs = 3, \
                  help='x,y,z size of hexahedral box [unchanged]')

parser.set_defaults(grid = ['0','0','0'])
parser.set_defaults(size  = ['0.0','0.0','0.0'])

(options, filenames) = parser.parse_args()

#--- setup file handles ---------------------------------------------------------------------------
files = []
if filenames == []:
  files.append({'name':'STDIN',
                'input':sys.stdin,
                'output':sys.stdout,
                'croak':sys.stderr,
               })
else:
  for name in filenames:
    if os.path.exists(name):
      files.append({'name':name,
                    'input':open(name),
                    'output':open(name+'_tmp','w'),
                    'croak':sys.stdout,
                    })

#--- loop over input files ------------------------------------------------------------------------
for file in files:
  if file['name'] != 'STDIN': file['croak'].write('\033[1m'+scriptName+'\033[0m: '+file['name']+'\n')
  else: file['croak'].write('\033[1m'+scriptName+'\033[0m\n')

  theTable = damask.ASCIItable(file['input'],file['output'],labels=False)
  theTable.head_read()

#--- interpret header ----------------------------------------------------------------------------
  info = {
          'grid':   numpy.zeros(3,'i'),
          'size':   numpy.zeros(3,'d'),
          'origin': numpy.zeros(3,'d'),
          'homogenization':  0,
          'microstructures': 0,
         }
  newInfo = {
          'grid':    numpy.zeros(3,'i'),
          'size':    numpy.zeros(3,'d'),
          'microstructures': 0,
         }
  extra_header = []

  for header in theTable.info:
    headitems = map(str.lower,header.split())
    if len(headitems) == 0: continue
    for synonym,alternatives in synonyms.iteritems():
      if headitems[0] in alternatives: headitems[0] = synonym
    if headitems[0] in mappings.keys():
      if headitems[0] in identifiers.keys():
        for i in xrange(len(identifiers[headitems[0]])):
          info[headitems[0]][i] = \
            mappings[headitems[0]](headitems[headitems.index(identifiers[headitems[0]][i])+1])
      else:
        info[headitems[0]] = mappings[headitems[0]](headitems[1])
    else:
      extra_header.append(header)

  file['croak'].write('grid     a b c:  %s\n'%(' x '.join(map(str,info['grid']))) + \
                      'size     x y z:  %s\n'%(' x '.join(map(str,info['size']))) + \
                      'origin   x y z:  %s\n'%(' : '.join(map(str,info['origin']))) + \
                      'homogenization:  %i\n'%info['homogenization'] + \
                      'microstructures: %i\n'%info['microstructures'])

  if numpy.any(info['grid'] < 1):
    file['croak'].write('invalid grid a b c.\n')
    continue
  if numpy.any(info['size'] <= 0.0):
    file['croak'].write('invalid size x y z.\n')
    continue

#--- read data ------------------------------------------------------------------------------------
  microstructure = numpy.zeros(info['grid'].prod(),'i')
  i = 0
  theTable.data_rewind()
  while theTable.data_read():
    items = theTable.data
    if len(items) > 2:
      if   items[1].lower() == 'of': items = [int(items[2])]*int(items[0])
      elif items[1].lower() == 'to': items = xrange(int(items[0]),1+int(items[2]))
      else:                          items = map(int,items)
    else:                            items = map(int,items)

    s = len(items)
    microstructure[i:i+s] = items
    i += s

#--- do work ------------------------------------------------------------------------------------

  newInfo['grid'] = numpy.array([{True:round(o*float(n.translate(None,'xX'))), False: round(float(n.translate(None,'xX')))}[n[-1].lower() == 'x'] for o,n in zip(info['grid'],options.grid)],'i')
  newInfo['size'] = numpy.array([{True:      o*float(n.translate(None,'xX')) , False:       float(n.translate(None,'xX')) }[n[-1].lower() == 'x'] for o,n in zip(info['size'],options.size)],'d')
  newInfo['grid'] = numpy.where(newInfo['grid'] <= 0  , info['grid'],newInfo['grid'])
  newInfo['size'] = numpy.where(newInfo['size'] <= 0.0, info['size'],newInfo['size'])

  multiplicity = []
  for j in xrange(3):
    multiplicity.append([])
    last = 0
    for i in xrange(info['grid'][j]):
      this = int((i+1)*float(newInfo['grid'][j])/info['grid'][j])
      multiplicity[j].append(this-last)
      last = this
  
  microstructure = microstructure.reshape(info['grid'],order='F')
  microstructure = numpy.repeat(
                   numpy.repeat(
                   numpy.repeat(microstructure,multiplicity[0], axis=0),
                                               multiplicity[1], axis=1),
                                               multiplicity[2], axis=2)

  newInfo['microstructures'] = microstructure.max()

#--- report ---------------------------------------------------------------------------------------
  if (any(newInfo['grid'] != info['grid'])):
    file['croak'].write('--> grid     a b c:  %s\n'%(' x '.join(map(str,newInfo['grid']))))
  if (any(newInfo['size'] != info['size'])):
    file['croak'].write('--> size     x y z:  %s\n'%(' x '.join(map(str,newInfo['size']))))
  if (newInfo['microstructures'] != info['microstructures']):
    file['croak'].write('--> microstructures: %i\n'%newInfo['microstructures'])
  
  if numpy.any(newInfo['grid'] < 1):
    file['croak'].write('invalid new grid a b c.\n')
    continue
  if numpy.any(newInfo['size'] <= 0.0):
    file['croak'].write('invalid new size x y z.\n')
    continue

#--- write header ---------------------------------------------------------------------------------
  theTable.labels_clear()
  theTable.info_clear()
  theTable.info_append(extra_header+[
    scriptID,
    "grid\ta %i\tb %i\tc %i"%(newInfo['grid'][0],newInfo['grid'][1],newInfo['grid'][2],),
    "size\tx %f\ty %f\tz %f"%(newInfo['size'][0],newInfo['size'][1],newInfo['size'][2],),
    "origin\tx %f\ty %f\tz %f"%(info['origin'][0],info['origin'][1],info['origin'][2],),
    "homogenization\t%i"%info['homogenization'],
    "microstructures\t%i"%(newInfo['microstructures']),
    ])
  theTable.head_write()
  theTable.output_flush()
  
# --- write microstructure information ------------------------------------------------------------
  formatwidth = int(math.floor(math.log10(microstructure.max())+1))
  theTable.data = microstructure.reshape((info['grid'][0],info['grid'][1]*info['grid'][2]),order='F').transpose()
  theTable.data_writeArray('%%%ii'%(formatwidth))
    
#--- output finalization --------------------------------------------------------------------------
  if file['name'] != 'STDIN':
    file['input'].close()
    file['output'].close()
    os.rename(file['name']+'_tmp',file['name'])
  
