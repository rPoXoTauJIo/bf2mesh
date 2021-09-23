import os
import logging
from math import sin, cos, radians

from .mesh import BF2Mesh
from .bf2types import D3DDECLTYPE, D3DDECLUSAGE, USED, UNUSED
from .io import read_float
from .io import read_float3
from .io import read_long
from .io import read_short
from .io import read_byte
from .io import read_matrix4
from .io import read_string
from .io import write_long
from .io import write_short
from .io import write_float3
from .io import write_byte
from .io import write_float
from .io import write_matrix4
from .io import write_string

class VisibleMesh(BF2Mesh):
    
    def __init__(self,
            filename=None,
            isSkinnedMesh=False,
            isBundledMesh=False,
            isStaticMesh=False):
        BF2Mesh.__init__(self, filename=filename,
                    isSkinnedMesh=isSkinnedMesh,
                    isBundledMesh=isBundledMesh,
                    isStaticMesh=isStaticMesh)

        ### MESH DATA ###
        self.head = _bf2head()  # header contains version info and some bfp4f data
        self.u1 = 0  # unknown byte, seems to be version flag for bfp4f

        # geom struct, hold materials info etc
        # staticmesh: geom0 = non-destroayble, geom1 = 3p destroyed
        # skinnedmesh: geom0 = 1p, geom1 = 3p
        # bundledmesh: geom0 = 1p, geom1 = 3p, geom2 = 3p wreck
        self.geomnum = 0
        self.geoms = [_bf2geom() for i in range(self.geomnum)]

        # vertex attributes table, holds info how vertex data packed in .vertices array
        self.vertattribnum = 0
        self.vertex_attributes = [_bf2vertattrib() for i in range(self.vertattribnum)]
        self.vertformat = 0  # bytes lenght for vertarray members, seems always to be 4? seems like DICE planned to have it for optimization later
        self.vertstride = 0  # bytes len for vertex data chunk

        # vertex data
        self.vertnum = 0  # number of vertices
        #self.vertices = tuple([_ for i in range( self.vertnum * self.vertstride / self.vertformat )])  # geom data, parse using attrib table
        self.vertices = []

        # indices
        # NOTE: indices are unsigned(?) short, therefor maximum indexed vertices per material is 32k
        self.indexnum = 0  # number of indices
        self.index = []  # indices array, values per-material

        self.u2 = 0  # some another bfp4f garbage..
        ### MESH DATA ###

        self.__enter__()

    def __enter__(self):
        if self.filename and not self.isLoaded:
            self.__meshfile = open(file=self.filename, mode='rb')
            self.__load()
            self.__meshfile.close()
        return self
    
    def __exit__(self, type, value, tracebacks):
        if self.__meshfile:
            if not self.__meshfile.closed:
                self.__meshfile.close()
    
    def __str__(self):
        retstr = []
        retstr.append(self.filename)
        retstr.append('header:\n%s' % str(self.head))
        retstr.append('u1: %s' % self.u1)
        
        raise NotImplementedError
        #return '\n'.join(retstr)
    
    @property
    def vertex_size(self):
        return sum([len(D3DDECLTYPE(v_attrib.vartype)) for v_attrib in self.vertex_attributes if v_attrib.flag is USED])
        
    def __load(self):
        self.__read_header()
        self.__read_u1()
        self.__read_geomnum()
        self.__read_geom_table()
        self.__read_vertattribnum()
        self.__read_vertattrib_table()
        self.__read_vertformat()
        self.__read_vertstride()
        self.__read_vertnum()
        self.__read_vertices()
        self.__read_indexnum()
        self.__read_indices()
        self.__read_u2()
        self.__load_lods_nodes_rigs()
        self.__load_lods_materials()
        
        # make sure we did read whole file, not missing any byte!
        if self.__meshfile.tell() == os.stat(self.filename).st_size:
            logging.debug('loaded %d bytes from %s' % (self.__meshfile.tell(), self.filename))
            self.isLoaded = True
        else:
            raise AttributeError('did not parsed all bytes from %s' % self.filename)
    
    def __read_header(self):
        logging.debug('starting reading header at %d' % self.__meshfile.tell())
        self.head.load(self.__meshfile)
        logging.debug('finished reading header at %d' % self.__meshfile.tell())
    
    def __read_u1(self):
        self.u1 = read_byte(self.__meshfile)
        logging.debug('u1 = %d' % self.u1)
    
    def __read_geomnum(self):
        self.geomnum = read_long(self.__meshfile)
        logging.debug('geomnum = %d' % self.geomnum)
    
    def __read_geom_table(self):
        logging.debug('starting reading geom table at %d' % self.__meshfile.tell())
        self.geoms = [_bf2geom() for i in range(self.geomnum)]
        for geom in self.geoms:
            geom.load(self.__meshfile)
        logging.debug('finished reading geom table at %d' % self.__meshfile.tell())

    def __read_vertattribnum(self):
        self.vertattribnum = read_long(self.__meshfile)
        logging.debug('vertattribnum = %d' % self.vertattribnum)
    
    def __read_vertattrib_table(self):
        logging.debug('starting reading vertattrib table at %d' % self.__meshfile.tell())
        self.vertex_attributes = [_bf2vertattrib() for i in range(self.vertattribnum)]
        for i in range(self.vertattribnum):
            self.vertex_attributes[i].load(self.__meshfile)
            logging.debug('attrib [{0}] = {1.flag}, {1.offset}, {1.usage}, {1.vartype}'.format(i, self.vertex_attributes[i]))
        logging.debug('finished reading vertattrib table at %d' % self.__meshfile.tell())

    def __read_vertformat(self):
        self.vertformat = read_long(self.__meshfile)
        logging.debug('vertformat = %d' % self.vertformat)

    def __read_vertstride(self):
        self.vertstride = read_long(self.__meshfile)
        logging.debug('vertstride = %d' % self.vertstride)

    def __read_vertnum(self):
        self.vertnum = read_long(self.__meshfile)
        logging.debug('vertnum = %d' % self.vertnum)

    def __read_vertices(self):
        logging.debug('starting reading vertex block at %d' % self.__meshfile.tell())
        data_num = int(self.vertstride / self.vertformat * self.vertnum)
        self.vertices = read_float(self.__meshfile, data_num)
        logging.debug('array size = %d' % len(self.vertices))
        logging.debug('finished reading vertex block at %d' % self.__meshfile.tell())
    
    def __read_indexnum(self):
        self.indexnum = read_long(self.__meshfile)
        logging.debug('indexnum = %d', self.indexnum)

    def __read_indices(self):
        logging.debug('starting reading index block at %d' % self.__meshfile.tell())
        self.index = read_short(self.__meshfile, self.indexnum)
        logging.debug('finished reading index block at %d' % self.__meshfile.tell())

    def __read_u2(self):
        if not self.isSkinnedMesh:
            self.u2 = read_long(self.__meshfile)
            logging.debug('u2 = %d' % self.u2)
    
    def __load_lods_nodes_rigs(self):
        logging.debug('starting reading lods tables at %d' % self.__meshfile.tell())
        for geom_id, geom in enumerate(self.geoms):
            logging.debug('reading geom%d at %d' % (geom_id, self.__meshfile.tell()))
            for lod_id, lod in enumerate(geom.lods):
                logging.debug('reading lod%d at %d' % (lod_id, self.__meshfile.tell()))
                lod.load_nodes_rigs(self.__meshfile, self.head.version, self.isBundledMesh, self.isSkinnedMesh)
        logging.debug('finished reading lods tables at %d' % (self.__meshfile.tell()))

    def __load_lods_materials(self):
        logging.debug('starting reading materials at %d' % (self.__meshfile.tell()))
        for geom_id, geom in enumerate(self.geoms):
            logging.debug('reading geom%d at %d' % (geom_id, self.__meshfile.tell()))
            for lod_id, lod in enumerate(geom.lods):
                logging.debug('reading lod%d at %d' % (lod_id, self.__meshfile.tell()))
                lod.load_materials(self.__meshfile, self.head.version, self.isSkinnedMesh)
        logging.debug('finished reading materials at %d' % (self.__meshfile.tell()))
    
    def export(self, filename=None, update_bounds=True):
        if not filename: filename = self.filename
        logging.debug('saving mesh as %s' % filename)

        dirname = os.path.dirname(filename)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        
        # update lods&materials bounds first
        if update_bounds: self.update_boundaries()

        with open(filename, 'wb') as vmesh:
            self.__export(vmesh)
            self.filename = filename
            
    def __export(self, fo):
        logging.debug('writing header at %d' % fo.tell())
        self.head.export(fo)
        write_byte(fo, self.u1)
        logging.debug('writing geom table at %d' % fo.tell())
        write_long(fo, self.geomnum)
        for geom in self.geoms:
            geom.export(fo)
        logging.debug('writing vertex attributes table at %d' % fo.tell())
        write_long(fo, self.vertattribnum)
        for vertex_attributes_table in self.vertex_attributes:
            vertex_attributes_table.export(fo)
        logging.debug('writing vertices block at %d' % fo.tell())
        write_long(fo, self.vertformat)
        write_long(fo, self.vertstride)
        write_long(fo, self.vertnum)
        logging.debug('writing vertices array at %d' % fo.tell())
        for value in self.vertices:
            write_float(fo, value)
        logging.debug('writing %d indices at %d' % (self.indexnum, fo.tell()))
        write_long(fo, self.indexnum)
        for value in self.index:
            write_short(fo, value)
        if not self.isSkinnedMesh: write_long(fo, self.u2)
        logging.debug('writing nodes at %d' % fo.tell())
        for geom in self.geoms:
            for lod in geom.lods:
                lod.export_nodes(fo, self.head.version, self.isBundledMesh, self.isSkinnedMesh)
        logging.debug('writing materials at %d' % fo.tell())
        for geom in self.geoms:
            for lod in geom.lods:
                lod.export_materials(fo, self.head.version, self.isSkinnedMesh)
        logging.debug('exported %d bytes' % fo.tell())
    
    def change_geoms_order(self, order):
        if len(order) != len(self.geoms):
            raise AttributeError('new order geoms number not equal, got %d, expected %d' % (len(order), len(self.geoms)))

        new_geoms = []
        new_vertices = []
        new_index = []

        # vertex_size = self.vertstride / self.vertformat
        vertex_size = sum([len(D3DDECLTYPE(v_attrib.vartype)) for v_attrib in self.vertex_attributes if v_attrib.flag is USED])
        for geomId in order:
            geom = self.geoms[geomId]
            for lod in geom.lods:
                for material in lod.materials:
                    vstart = material.vstart * vertex_size
                    vend = vstart + material.vnum * vertex_size
                    new_vertices.extend(self.vertices[vstart:vend])

                    new_index.extend(self.index[material.istart:material.istart+material.inum])
                    
                    material.vstart = int(len(new_vertices) / vertex_size) - material.vnum
                    material.istart = len(new_index) - material.inum
            new_geoms.append(geom)
        
        self.geoms = new_geoms
        self.vertices = new_vertices
        self.index = new_index
    
    def translate(self, offset):
        logging.debug('translating with offset of %s' % str(offset))
        new_vertices = []

        for geomId, geom in enumerate(self.geoms):
            geom = self.geoms[geomId]
            for lodId, lod in enumerate(geom.lods):
                for materialId, material in enumerate(lod.materials):
                    logging.debug('creating copy of geoms[%d].lods[%d].materials[%d] vertices array' % (geomId, lodId, materialId))

                    vstart = material.vstart * self.vertex_size
                    vend = vstart + material.vnum * self.vertex_size

                    _material_vertices = list(self.vertices[vstart:vend])
                    logging.debug('material vertices buffer [%d*%d:%d + %d*%d][%d]' % (material.vstart, self.vertex_size,
                                                                                               vstart, material.vnum, self.vertex_size,
                                                                                               len(_material_vertices)))
                    for i in range(0, len(_material_vertices), self.vertex_size):
                        vertex = _material_vertices[i:i + self.vertex_size]
                        logging.debug('geoms[%d].lods[%d].materials[%d] vertex buffer[%d:%d][%d]: %s' % (geomId, lodId, materialId,
                                                                                                        i, i + self.vertex_size, self.vertex_size, vertex))

                        for attrib in self.vertex_attributes:
                            if attrib.usage == D3DDECLUSAGE.POSITION and attrib.flag != UNUSED:
                                vertoffset = int(attrib.offset / self.vertformat)
                                break
                        
                        for valueId, value in enumerate(offset):
                            logging.debug('updating vertex.POSITION[%d]: %s += %s' % (valueId, vertex[vertoffset+valueId], value))
                            vertex[vertoffset+valueId] += value

                        new_vertices.extend(vertex)
                        logging.debug('extended vertices array to %d' % (len(new_vertices)))
        
        logging.debug('replacing old vertices array of %d size by new vertices array of %d size' % (len(self.vertices), len(new_vertices)))
        self.vertices = tuple(new_vertices)
    
    def rotate(self, rotation):
        # sorry i suck at math so this much code

        # rotate around forward(red) axis
        # pitch
        def Rpitch(position, angle):
            x = position[0]
            y = position[1]
            z = position[2]

            newX = x
            newY = y * cos(angle) - z * sin(angle)
            newZ = y * sin(angle) + z * cos(angle)

            return (newX, newY, newZ)

        # rotate around vertical(green) axis
        # yaw
        def Ryaw(position, angle):
            x = position[0]
            y = position[1]
            z = position[2]

            newX = x * cos(angle) + z * sin(angle)
            newY = y
            newZ = z * cos(angle) - x * sin(angle)

            return (newX, newY, newZ)

        # rotate around side(blue) axis
        # roll
        def Rroll(position, angle):
            x = position[0]
            y = position[1]
            z = position[2]

            newX = x * cos(angle) - y * sin(angle)
            newY = x * sin(angle) + y * cos(angle)
            newZ = z

            return (newX, newY, newZ)

        logging.debug('rotating by %s' % str(rotation))
        float3 = [axis for axis in rotation]
        yaw = radians(float3[0])
        pitch = radians(float3[1])
        roll = radians(float3[2])

        new_vertices = []

        for geomId, geom in enumerate(self.geoms):
            geom = self.geoms[geomId]
            for lodId, lod in enumerate(geom.lods):
                for materialId, material in enumerate(lod.materials):
                    logging.debug('creating copy of geoms[%d].lods[%d].materials[%d] vertices array' % (geomId, lodId, materialId))

                    vstart = material.vstart * self.vertex_size
                    vend = vstart + material.vnum * self.vertex_size

                    _material_vertices = list(self.vertices[vstart:vend])
                    logging.debug('material vertices buffer [%d*%d:%d + %d*%d][%d]' % (material.vstart, self.vertex_size,
                                                                                            vstart, material.vnum, self.vertex_size,
                                                                                            len(_material_vertices)))
                    for i in range(0, len(_material_vertices), self.vertex_size):
                        vertex = _material_vertices[i:i + self.vertex_size]
                        logging.debug('geoms[%d].lods[%d].materials[%d] vertex buffer[%d:%d][%d]: %s' % (geomId, lodId, materialId,
                                                                                                        i, i + self.vertex_size, self.vertex_size, vertex))

                        for attrib in self.vertex_attributes:
                            if attrib.flag == UNUSED: continue
                            if attrib.usage in [D3DDECLUSAGE.POSITION, D3DDECLUSAGE.NORMAL, D3DDECLUSAGE.TANGENT]:
                                vertoffset = int(attrib.offset / self.vertformat)
                                data = vertex[vertoffset:vertoffset+len(D3DDECLTYPE(attrib.vartype))]
                                logging.debug('updating vertex.%s: %s' % (D3DDECLUSAGE(attrib.usage).name, data))
                                new_data = Ryaw(Rpitch(Rroll(data, roll), pitch), yaw)
                                vertex[vertoffset:vertoffset+len(D3DDECLTYPE(attrib.vartype))] = new_data
                                logging.debug('updated vertex.%s: %s' % (D3DDECLUSAGE(attrib.usage).name, data))

                        new_vertices.extend(vertex)
                        logging.debug('extended vertices array to %d' % (len(new_vertices)))
        
        logging.debug('replacing old vertices array of %d size by new vertices array of %d size' % (len(self.vertices), len(new_vertices)))
        self.vertices = tuple(new_vertices)
    
    def canMerge(self, other):
        # support only "same" meshes for now
        if len(self.geoms) != len(other.geoms):
            logging.debug('geoms %d != geoms %d %s: %s' % (len(self.geoms), len(other.geoms), self.filename, other.filename) )
            return False
        for geomId, geom in enumerate(self.geoms):
            if len(geom.lods) != len(other.geoms[geomId].lods):
                logging.debug('geom[%d].lods %d != geom[%d].lods %d %s: %s' % (geomId, len(geom.lods), geomId, len(other.geoms[geomId].lods), self.filename, other.filename) )
                return False
            for lodId, lod in enumerate(geom.lods):
                if len(lod.materials) != len(other.geoms[geomId].lods[lodId].materials):
                    logging.debug('geom[%d].lod[%d].materials %d != geom[%d].lod[%d].materials %d %s: %s' % (geomId, lodId, len(lod.materials), geomId, lodId, len(other.geoms[geomId].lods[lodId].materials), self.filename, other.filename) )
                    return False
                for matId, material in enumerate(lod.materials):
                    other_material = other.geoms[geomId].lods[lodId].materials[matId]
                    if material.alphamode != other_material.alphamode:
                        logging.debug('geom[%d].lod[%d].material[%d].alphamode %d != geom[%d].lod[%d].material[%d].alphamode %s %s: %s' % (geomId, lodId, matId, material.alphamode, geomId, lodId, matId, other_material.alphamode, self.filename, other.filename) )
                        return False
                    if material.fxfile != other_material.fxfile:
                        logging.debug('geom[%d].lod[%d].material[%d].fxfile %s != geom[%d].lod[%d].material[%d].fxfile %s %s: %s' % (geomId, lodId, matId, material.fxfile, geomId, lodId, matId, other_material.fxfile, self.filename, other.filename) )
                        return False
                    if material.technique != other_material.technique:
                        logging.debug('geom[%d].lod[%d].material[%d].technique %s != geom[%d].lod[%d].material[%d].technique %s %s: %s' % (geomId, lodId, matId, material.technique, geomId, lodId, matId, other_material.technique, self.filename, other.filename) )
                        return False
                    if material.maps != other_material.maps:
                        logging.debug('geom[%d].lod[%d].material[%d] maps != geom[%d].lod[%d].material[%d] maps %s: %s' % (geomId, lodId, matId, geomId, lodId, matId, self.filename, other.filename) )
                        return False
        if len(self.vertex_attributes) != len(other.vertex_attributes):
            logging.debug('vertex_attributes %d != vertex_attributes %d %s: %s' % (len(self.vertex_attributes), len(other.vertex_attributes), self.filename, other.filename) )
            return False
        for attribId, attrib in enumerate(self.vertex_attributes):
            if attrib != other.vertex_attributes[attribId]:
                logging.debug('vertex_attributes[%d] %s != vertex_attributes[%d] %s %s: %s' % (attribId, str(attrib), attribId, str(attrib), self.filename, other.filename) )
                return False
        #if self.vertex_size != other.vertex_size: return False

        # TODO: check for arrays sizes
        # NOTE: indices are unsigned short max

        # passed checks, can merge
        return True

    # DELET THIS IF YOU FEEL CAN WRITE BETTER
    def merge(self, other):
        logging.debug('merging %s to %s' % (other.filename, self.filename))
        ####################################################
        # I'M VERY SORRY FUTURE ME IF YOU HAVE TO DEBUG THIS
        ####################################################
        if not self.canMerge(other): return NotImplementedError

        new_vertices = []
        new_index = []
        vstart = 0
        istart = 0
        vertnum = 0
        indexnum = 0

        # TODO: make merge as transaction?

        for geomId, geom in enumerate(self.geoms):
            for lodId, lod in enumerate(geom.lods):
                for materialId, material in enumerate(lod.materials):
                    logging.debug('adding vertices from geoms[%d].lods[%d].materials[%d]' % (geomId, lodId, materialId))
                    # adding old data
                    _vstart = material.vstart * self.vertex_size
                    _vend = _vstart + self.vertex_size * material.vnum
                    new_vertices.extend(self.vertices[_vstart:_vend])
                    logging.debug('extended vertices array to %d by self.vertices[%d:%d]' % (len(new_vertices), _vstart, _vend))
                    new_index.extend(self.index[material.istart:material.istart + material.inum])
                    logging.debug('extended index array to %d by self.index[%d:%d]' % (len(new_index), material.istart, material.istart + material.inum))

                    # adding new data
                    other_material = other.geoms[geomId].lods[lodId].materials[materialId]
                    _vstart = other_material.vstart * other.vertex_size
                    _vend = _vstart + other.vertex_size * other_material.vnum
                    new_vertices.extend(other.vertices[_vstart:_vend])
                    logging.debug('extended vertices array to %d by other.vertices[%d:%d]' % (len(new_vertices), _vstart, _vend))
                    for indexId in range(other_material.inum):
                        index = other.index[other_material.istart + indexId]
                        corrected_index = index + material.vnum
                        if corrected_index > int('0xffff', 16): raise OverflowError
                        new_index.append(corrected_index)
                    logging.debug('extended index array to %d by other.index[%d:%d], corrected by materials[%d].vnum %d' % (
                                                                                                        len(new_index),
                                                                                                        other_material.istart,
                                                                                                        other_material.istart + other_material.inum,
                                                                                                        materialId,
                                                                                                        material.vnum))
                    
                    # correcting material numbers
                    logging.debug('corecting materials[%d].vnum = %d, materials[%d].inum = %d' % (
                                                                                                materialId,
                                                                                                material.vnum,
                                                                                                materialId,
                                                                                                material.inum))
                    material.vnum += other_material.vnum
                    material.inum += other_material.inum
                    logging.debug('corrected materials[%d].vnum = %d, materials[%d].inum = %d' % (
                                                                                                materialId,
                                                                                                material.vnum,
                                                                                                materialId,
                                                                                                material.inum))

                    # correcting material offsets
                    logging.debug('corecting materials[%d].vstart = %d, materials[%d].istart = %d' % (
                                                                                                materialId,
                                                                                                material.vstart,
                                                                                                materialId,
                                                                                                material.istart))
                    material.vstart = vstart
                    material.istart = istart
                    logging.debug('corrected materials[%d].vstart = %d, materials[%d].istart = %d' % (
                                                                                                materialId,
                                                                                                material.vstart,
                                                                                                materialId,
                                                                                                material.istart))

                    vstart += material.vnum
                    istart += material.inum
                    
                    #vertnum_old = vertnum
                    vertnum += material.vnum
                    indexnum += material.inum

        
        logging.debug('replacing old vertices array of %d size by new vertices array of %d size' % (len(self.vertices), len(new_vertices)))
        self.vertices = tuple(new_vertices)
        logging.debug('replacing old index array of %d size by new index array of %d size' % (len(self.index), len(new_index)))
        self.index = tuple(new_index)
        logging.debug('self.vertnum: %d -> %d' % (self.vertnum, vertnum))
        self.vertnum = vertnum
        logging.debug('self.indexnum: %d -> %d' % (self.indexnum, indexnum))
        self.indexnum = indexnum
    
    def update_boundaries(self):
        logging.debug('updating %s boundaries' % self.filename)
        class _vertex(object):
            pass

        for geomId, geom in enumerate(self.geoms):
            for lodId, lod in enumerate(geom.lods):
                lod_min = list(lod.min)
                lod_max = list(lod.max)
                logging.debug('self.geoms[%d].lods[%d].min = %s' % (geomId, lodId, lod_min))
                logging.debug('self.geoms[%d].lods[%d].max = %s' % (geomId, lodId, lod_max))
                for materialId, material in enumerate(lod.materials):
                    if not self.isSkinnedMesh and self.head.version == 11:
                        material_min = list(material.mmin)
                        material_max = list(material.mmax)
                        logging.debug('self.geoms[%d].lods[%d].materials[%d].mmin = %s' % (geomId, lodId, materialId, material_min))
                        logging.debug('self.geoms[%d].lods[%d].materials[%d].mmax = %s' % (geomId, lodId, materialId, material_max))
                    for vertId in range(material.vnum):
                        # create vertex
                        _start = (material.vstart + vertId) * self.vertex_size
                        _end = _start + self.vertex_size
                        vertexBuffer = self.vertices[_start:_end]
                        vertex = _vertex()
                        for attrib in self.vertex_attributes:
                            if attrib.flag is UNUSED: continue
                            _start = int(attrib.offset / self.vertformat)
                            _end = _start + len(D3DDECLTYPE(attrib.vartype))
                            setattr(vertex, D3DDECLUSAGE(attrib.usage).name, vertexBuffer[_start:_end])
                        # update material and lod bounds
                        if not self.isSkinnedMesh and self.head.version == 11:
                            for id_axis, axis in enumerate(material_min):
                                position = getattr(vertex, 'POSITION')
                                if position[id_axis] < material_min[id_axis]:
                                    logging.debug('geoms[%d].lods[%d].materials[%d].mmin(%d): %s > %s, updating' % (geomId, lodId, materialId, id_axis, material_min[id_axis], position[id_axis]))
                                    material_min[id_axis] = position[id_axis]
                                if position[id_axis] < lod_min[id_axis]:
                                    logging.debug('geoms[%d].lods[%d].min(%d): %s > %s, updating' % (geomId, lodId, id_axis, lod_min[id_axis], position[id_axis]))
                                    lod_min[id_axis] = position[id_axis]
                            for id_axis, axis in enumerate(material_max):
                                if position[id_axis] > material_max[id_axis]:
                                    logging.debug('geoms[%d].lods[%d].materials[%d].mmin(%d): %s > %s, updating' % (geomId, lodId, materialId, id_axis, material_max[id_axis], position[id_axis]))
                                    material_max[id_axis] = position[id_axis]
                                if position[id_axis] > lod_max[id_axis]:
                                    logging.debug('geoms[%d].lods[%d].min(%d): %s > %s, updating' % (geomId, lodId, id_axis, lod_max[id_axis], position[id_axis]))
                                    lod_max[id_axis] = position[id_axis]
                    if not self.isSkinnedMesh and self.head.version == 11:
                        material.mmin = tuple(material_min)
                        material.mmax = tuple(material_max)
                lod.min = tuple(lod_min)
                lod.max = tuple(lod_max)


class _bf2head:
    """
    Holds version info + some unknown bytes

    """
    def __init__(self):
        self.u1 = None
        self.version = None
        self.u3 = None
        self.u4 = None
        self.u5 = None

    def load(self, fo):
        self.u1 = read_long(fo)
        self.version = read_long(fo)
        self.u3 = read_long(fo)
        self.u4 = read_long(fo)
        self.u5 = read_long(fo)
        logging.debug('head.u1 = %d' % self.u1)
        logging.debug('head.version = %d' % self.version)
        logging.debug('head.u3 = %d' % self.u3)
        logging.debug('head.u4 = %d' % self.u4)
        logging.debug('head.u5 = %d' % self.u5)
    
    def export(self, fo):
        write_long(fo, self.u1)
        write_long(fo, self.version)
        write_long(fo, self.u3)
        write_long(fo, self.u4)
        write_long(fo, self.u5)


    def __eq__(self, other):
        if self.u1 != other.u1: return False
        if self.version != other.version: return False
        if self.u3 != other.u3: return False
        if self.u4 != other.u4: return False
        if self.u5 != other.u5: return False
        return True
    
    def __str__(self):
        return '\n'.join([
                        'head.u1 = ' + str(self.u1),
                        'head.version = ' + str(self.version),
                        'head.u3 = ' + str(self.u3),
                        'head.u4 = ' + str(self.u4),
                        'head.u5 = ' + str(self.u5)])

class _bf2mat:
    def __init__(self):
        self.alphamode = None # transparency enableddisabled
        self.fxfile = None # shader
        self.technique = None # transparency type

        # textures
        self.mapnum = 0
        self.maps = [b'' for i in range(self.mapnum)]

        # geom data
        self.vstart = None # vertex array offset
        self.istart = None # index array offset
        self.inum = None # amount of indices
        self.vnum = None # amount of vertices

        # unknowns
        self.u4 = None
        self.u5 = None

        # material boundaries
        self.mmin = None
        self.mmax = None

    def __eq__(self, other):
        if self.alphamode != other.alphamode:
            logging.debug('\nmaterial.alphamode = %r\nother.alphamode = %r' % (self.alphamode, other.alphamode))
            return False
        if self.fxfile != other.fxfile:
            logging.debug('\nmaterial.fxfile = %s\nother.fxfile = %s' % (self.fxfile, other.fxfile))
            return False
        if self.technique != other.technique:
            logging.debug('\nmaterial.technique = %s\nother.technique = %s' % (self.technique, other.technique))
            return False
        if self.mapnum != other.mapnum:
            logging.debug('\nmaterial.mapnum = %d\nother.mapnum = %d' % (self.mapnum, other.mapnum))
            return False
        if self.maps != other.maps:
            logging.debug('\nmaterial.maps = %s\nother.maps = %s' % (str(self.maps), str(other.maps)))
            return False
        if self.vstart != other.vstart:
            logging.debug('\nmaterial.vstart = %d\nother.vstart = %d' % (self.vstart, other.vstart))
            return False
        if self.istart != other.istart:
            logging.debug('\nmaterial.istart = %d\nother.vstart = %d' % (self.istart, other.istart))
            return False
        if self.inum != other.inum:
            logging.debug('\nmaterial.inum = %d\nother.inum = %d' % (self.inum, other.inum))
            return False
        if self.vnum != other.vnum:
            logging.debug('\nmaterial.vnum = %d\nother.vnum = %d' % (self.vnum, other.vnum))
            return False
        if self.u4 != other.u4:
            logging.debug('\nmaterial.u4 = %d\nother.u4 = %d' % (self.u4, other.u4))
            return False
        if self.u5 != other.u5:
            logging.debug('\nmaterial.u5 = %d\nother.u5 = %d' % (self.u5, other.u5))
            return False
        if self.mmin != other.mmin:
            logging.debug('\nmaterial.mmin = (%d, %d, %d)\nother.mmin = (%d, %d, %d)' % (*self.mmin, *other.mmin))
            return False
        return True

    def load(self, fo, version, isSkinnedMesh):
        if not isSkinnedMesh:
            self.alphamode = read_long(fo)
            logging.debug('alphamode = %d' % self.alphamode)
        self.fxfile = read_string(fo)
        self.technique = read_string(fo)
        logging.debug('fxfile = %s' % self.fxfile)
        logging.debug('technique = %s' % self.technique)

        self.mapnum = read_long(fo)
        self.maps = [read_string(fo) for i in range(self.mapnum)]
        logging.debug('mapnum = %d' % self.mapnum)
        for texturename in self.maps:
            logging.debug('map = %s' % texturename)

        self.vstart = read_long(fo)
        self.istart = read_long(fo)
        self.inum = read_long(fo)
        self.vnum = read_long(fo)
        logging.debug('vstart = %d' % self.vstart)
        logging.debug('istart = %d' % self.istart)
        logging.debug('inum = %d' % self.inum)
        logging.debug('vnum = %d' % self.vnum)

        self.u4 = read_long(fo)
        self.u5 = read_long(fo)
        logging.debug('u4 = %d' % self.u4)
        logging.debug('u5 = %d' % self.u5)

        if not isSkinnedMesh and version == 11:
            self.mmin = read_float3(fo)
            self.mmax = read_float3(fo)
            logging.debug('mmin = ({})'.format(*self.mmin))
            logging.debug('mmax = ({})'.format(*self.mmax))

    def export(self, fo, version, isSkinnedMesh):
        if not isSkinnedMesh:
            write_long(fo, self.alphamode)

        write_string(fo, self.fxfile)
        write_string(fo, self.technique)

        write_long(fo, self.mapnum)
        for texturename in self.maps:
            write_string(fo, texturename)

        write_long(fo, self.vstart)
        write_long(fo, self.istart)
        write_long(fo, self.inum)
        write_long(fo, self.vnum)

        write_long(fo, self.u4)
        write_long(fo, self.u5)

        if not isSkinnedMesh and version == 11:
            write_float3(fo, *self.mmin)
            write_float3(fo, *self.mmax)

class _bf2geom:
    """
    Geometry structure table, stores info about lods inheritance from geoms, and materials

    """
    def __init__(self):
        self.lodnum = 0
        self.lods = [_bf2lod() for i in range(self.lodnum)]

    def load(self, fo):
        self.lodnum = read_long(fo)
        self.lods = [_bf2lod() for i in range(self.lodnum)]
        logging.debug('geom.lodnum = %d' % self.lodnum)
    
    def export(self, fo):
        write_long(fo, self.lodnum)

    # NOTE: eq should be comparing only if trees structure same, DO NOT compare content
    def __eq__(self, other):
        if self.lodnum != other.lodnum: return False
        if len(self.lods) != len(other.lods): return False
        return True

class _bf2lod:

    def __init__(self):
        # boundaries
        self.min = None
        self.max = None
        self.pivot = None  # some unknown float3 for .version <=6

        # rigs, only for skinned meshes
        self.rignum = 0
        self.rigs = [_bf2rig() for i in range(self.rignum)]

        # nodes for bundled and staticmeshes
        # seems like those a geomPart objects for animated springs\rotbundles
        self.nodenum = 0
        self.nodes = []  # matrix4 * .nodenum

        # materials stores info about vertices&indices offsets + textures&shaders
        self.matnum = 0
        self.materials = [_bf2mat() for i in range(self.matnum)]

        # StdSample object for LMing statics
        self.sample = None
    
    def __eq__(self, other):
        if self.min != other.min:
            logging.debug('\nlod.min = (%g, %g, %g)\nother.min = (%g, %g, %g)' % (*self.min, *other.min))
            return False
        if self.max != other.max:
            logging.debug('\nlod.max = (%g, %g, %g)\nother.max = (%g, %g, %g)' % (*self.max, *other.max))
            return False
        if self.pivot != other.pivot:
            logging.debug('\nlod.pivot = (%g, %g, %g)\nother.pivot = (%g, %g, %g)' % (*self.pivot, *other.pivot))
            return False
        if self.rignum != other.rignum:
            logging.debug('\nlod.rignum = %d\nother.rignum = %d' % (self.rignum, other.rignum))
            return False
        for rigId, rig in enumerate(self.rigs):
            other_rig = other.rigs[rigId]
            if rig != other_rig:
                logging.debug('\nlod.rigs[%d] = %s\nother.rigs[%d] = %s' % (rigId, str(rig), rigId, str(other_rig)))
                return False
        if self.nodenum != other.nodenum:
            logging.debug('\nlod.nodenum = %d\nother.nodenum = %d' % (self.nodenum, other.nodenum))
            return False
        for nodeId, node in enumerate(self.nodes):
            other_node = other.nodes[nodeId]
            if node != other_node:
                logging.debug('\nlod.nodes[%d] = %s\nother.nodes[%d] = %s' % (nodeId, str(node), nodeId, str(other_node)))
                return False
        if self.matnum != other.matnum:
            logging.debug('\nlod.matnum = %d\nother.matnum = %d' % (self.matnum, other.matnum))
            return False
        for materialId, material in enumerate(self.materials):
            other_material = other.materials[materialId]
            if material != other_material:
                logging.debug('\nlod.material[%d] = %s\nother.material[%d] = %s' % (materialId, str(material), materialId, str(other_material)))
                return False
        return True

    # loading nodes data for bundledmeshes
    # loading rigs data for skinnedmeshes
    # loading boundaries for staticmesh
    def load_nodes_rigs(self, fo, version, isBundledMesh, isSkinnedMesh):
        self.min = read_float3(fo)
        self.max = read_float3(fo)
        logging.debug('lod.min = ({})'.format(*self.min))
        logging.debug('lod.max = ({})'.format(*self.max))

        if version <= 6: # some old meshes, version 4, 6
            self.pivot = read_float3(fo)
            logging.debug('lod.pivot = ({})'.format(*self.pivot))

        if isSkinnedMesh:
            self.rignum = read_long(fo)
            logging.debug('lod.rignum = %d' % (self.rignum))
            if self.rignum > 0:
                self.rigs = [_bf2rig() for i in range(self.rignum)]
                for rig in self.rigs:
                    rig.load(fo)
        else:
            self.nodenum = read_long(fo)
            logging.debug('lod.nodenum = %d' % (self.nodenum))
            if not isBundledMesh:
                for _ in range(self.nodenum):
                    self.nodes.append(read_matrix4(fo))
    
    def export_nodes(self, fo, version, isBundledMesh, isSkinnedMesh):
        write_float3(fo, *self.min)
        write_float3(fo, *self.max)

        if version <= 6:
            write_float3(fo, *self.pivot)
        
        if isSkinnedMesh:
            write_long(fo, self.rignum)
            for rig in self.rigs:
                rig.export(fo)
        else:
            write_long(fo, self.nodenum)
            if not isBundledMesh:
                for node in self.nodes:
                    write_matrix4(fo, node)
    
    def load_materials(self, fo, version, isSkinnedMesh):
        self.matnum = read_long(fo)
        logging.debug('lod.matnum = %d' % (self.matnum))
        self.materials = [_bf2mat() for i in range(self.matnum)]
        for material_id, material in enumerate(self.materials):
            logging.debug('reading material%d at %d' % (material_id, fo.tell()))
            material.load(fo, version, isSkinnedMesh)
    
    def export_materials(self, fo, version, isSkinnedMesh):
        write_long(fo, self.matnum)
        for material in self.materials:
            material.export(fo, version, isSkinnedMesh)

class _bf2rig:
    def __init__(self):
        self.bonenum = 0
        self.bones = [_bf2bone() for i in range(self.bonenum)]

    def __eq__(self, other):
        if self.bonenum != other.bonenum:
            logging.debug('\nrig.bonenum = %d\nother.bonenum = %d' % (self.bonenum, other.bonenum))
            return False
        for boneId, bone in enumerate(self.bones):
            other_bone = other.bones[boneId]
            if bone != other_bone:
                logging.debug('\nrig.bones[%d] = %s\nrig.bones[%d] = %s' % (boneId, str(bone), boneId, str(other_bone)))
                return False
        return True

    def load(self, fo):
        self.bonenum = read_long(fo)
        if self.bonenum > 0:
            self.bones = [_bf2bone() for i in range(self.bonenum)]
            for bone in self.bones:
                bone.id = read_long(fo)
                bone.matrix = read_matrix4(fo)
    
    def export(self, fo):
        write_long(fo, self.bonenum)
        for bone in self.bones:
            write_long(fo, bone.id)
            write_matrix4(fo, bone.matrix)

class _bf2bone:

    def __init__(self):
        self.id = None
        self.matrix = []
    
    def __eq__(self, other):
        if self.id != other.id:
            logging.debug('\nbone.id = %d\nother.id = %d' % (self.id, other.id))
            return False
        if self.matrix != other.matrix:
            logging.debug('\nbone.matrix = %s\nother.id = %s' % (str(self.matrix), str(other.matrix)))
            return False
        return True

class _bf2vertattrib:
    
    """
    Vertex attributes table, holds info how vertex data packed in .vertices array

    """
    def __init__(self, flag=None, offset=None, vartype=None, usage=None):
        self.flag = flag # USED\UNUSED
        self.offset = offset # offset from block start, in bytes
        self.vartype = vartype # DX SDK 'Include/d3d9types.h' enum _D3DDECLTYPE
        self.usage = usage # DX SDK 'Include/d3d9types.h' enum _D3DDECLUSAGE
    
    def load(self, fo):
        self.flag = read_short(fo)
        self.offset = read_short(fo)
        self.vartype = read_short(fo)
        self.usage = read_short(fo)
    
    def export(self, fo):
        write_short(fo, self.flag)
        write_short(fo, self.offset)
        write_short(fo, self.vartype)
        write_short(fo, self.usage)
    
    def __eq__(self, other):
        if not isinstance(other, _bf2vertattrib): return False
        if self.flag != other.flag: return False
        if self.offset != other.offset: return False
        if self.vartype != other.vartype: return False
        if self.usage != other.usage: return False
        return True
    
    def __str__(self):
        return 'flag: %s, offset: %s, vartype: %s of size %s, usage: %s' % (self.flag, self.offset, D3DDECLTYPE(self.vartype), len(D3DDECLTYPE(self.vartype)), D3DDECLUSAGE(self.usage).name)
