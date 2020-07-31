from invoke import task, run

#from fabric.api import local, lcd, get, env
#from fabric.operations import require, prompt
#from fabric.utils import abort
import requests
import rdflib
import getpass
import os.path
import os
import setlr
from os import listdir
from rdflib import *

import logging

CHEAR_DIR='chear.d/'
HHEAR_DIR='hhear.d/'
SETL_FILE='ontology.setl.ttl'

ontology_setl = Namespace('https://hadatac.org/setl/')
setl = Namespace('http://purl.org/twc/vocab/setl/')
prov = Namespace('http://www.w3.org/ns/prov#')
skos = Namespace('http://www.w3.org/2004/02/skos/core#')
dc = Namespace('http://purl.org/dc/terms/')
pv = Namespace('http://purl.org/net/provenance/ns#')
csvw = Namespace('http://www.w3.org/ns/csvw#')

logging_level = logging.INFO
logging.basicConfig(level=logging_level)


@task
def buildchear(ctx):
    setl_graph = Graph()
    setl_graph.parse(SETL_FILE,format="turtle")
    cwd = os.getcwd()
    formats = ['ttl','owl','json']
    ontology_output_files = [setl_graph.resource(URIRef('file://'+cwd+'/chear.'+x)) for x in formats]
    print (len(setl_graph))
    for filename in os.listdir(CHEAR_DIR):
        if not filename.endswith('.ttl') or filename.startswith('#'):
            continue
        print('Adding fragment', filename)

        fragment = setl_graph.resource(BNode())
        for ontology_output_file in ontology_output_files:
            print(ontology_output_file.identifier, list(ontology_output_file[prov.wasGeneratedBy]))
            ontology_output_file.value(prov.wasGeneratedBy).add(prov.used, fragment)
        fragment.add(RDF.type, setlr.void.Dataset)
        fragment_extract = setl_graph.resource(BNode())
        fragment.add(prov.wasGeneratedBy, fragment_extract)
        fragment_extract.add(RDF.type, setl.Extract)
        fragment_extract.add(prov.used, URIRef('file://'+CHEAR_DIR+filename))

    setlr._setl(setl_graph)

@task
def buildhhear(ctx):
    setl_graph = Graph()
    setl_graph.parse('hhear-ontology.setl.ttl',format="turtle")
    cwd = os.getcwd()
    formats = ['ttl','owl','json']
    ontology_output_files = [setl_graph.resource(URIRef('file://'+cwd+'/hhear.'+x)) for x in formats]
    print (len(setl_graph))
    for filename in os.listdir(HHEAR_DIR):
        if not filename.endswith('.ttl') or filename.startswith('#'):
            continue
        print('Adding fragment', filename)

        fragment = setl_graph.resource(BNode())
        for ontology_output_file in ontology_output_files:
            print(ontology_output_file.identifier, list(ontology_output_file[prov.wasGeneratedBy]))
            ontology_output_file.value(prov.wasGeneratedBy).add(prov.used, fragment)
        fragment.add(RDF.type, setlr.void.Dataset)
        fragment_extract = setl_graph.resource(BNode())
        fragment.add(prov.wasGeneratedBy, fragment_extract)
        fragment_extract.add(RDF.type, setl.Extract)
        fragment_extract.add(prov.used, URIRef('file://'+HHEAR_DIR+filename))

    setlr._setl(setl_graph)

@task
def chear2hhear(c, inputfile, outputfile):
    import openpyxl
    import re
    import pandas as pd

    mappings = {}
    mappings.update(dict([(row['label_uri'], row['numeric_uri'])
                          for i, row in pd.read_csv('sio_mappings.csv').iterrows()]))
    mappings.update(dict([(row['label_uri'], row['numeric_uri'])
                          for i, row in pd.read_csv('chear2hhear_mappings.csv').iterrows()]))

    wb = openpyxl.load_workbook(inputfile)
    for sheet in wb:
        for row in sheet.rows:
            for cell in row:
                if isinstance(cell.value, str):
                    cellValues = []
                    for c in re.split('\\s*[,&]\\s*', cell.value):
                        if c in mappings:
                            print('Replacing',c,'with',mappings[c])
                            c = mappings[c]
                        cellValues.append(c)
                    cell.value = ', '.join(cellValues)

    wb.save(outputfile)

def load_namespaces():
    url = 'http://www.hadatac.org/config/hhear/namespaces-hhear-v5.properties'
    properties = requests.get(url, headers={"User-Agent": "requests"}).text
    properties = [row for row in properties.split('\n') if len(row) > 0]
    properties = dict([tuple(row.split('=')) for row in properties])
    properties = dict([(key,value.split(',')[0])
                        for key, value in properties.items()])
    return properties

@task
def sdd2owl(c, inputfile, ontology, outputfile, infosheet="InfoSheet"):
    import openpyxl
    import re
    import pandas as pd
    import json
    cwd = os.getcwd()

    setl_graph = Graph()
    setl_graph.parse('sdd_owl_semantics.setl.ttl',format="turtle")

    sddns = rdflib.Namespace('http://purl.org/twc/sdd/setl/')

    tab_config = {
        "Data_Dictionary" : sddns.dm_table,
        "Codebook" : sddns.codebook_table,
        "Code_Mappings" : sddns.codemapping_table,
        "Timeline" : sddns.timeline_table
    }

    wb = openpyxl.load_workbook(inputfile)

    infosheet_tab = wb[infosheet]
    infosheet_dict = dict([(row[0].value,row[1].value) for row in infosheet_tab])

    infosheet_resource = setl_graph.resource(sddns.info_sheet)
    infosheet_resource.add(rdflib.RDF.type, setl.Excel)
    infosheet_resource.add(setl.sheetname, rdflib.Literal(infosheet))
    gen = infosheet_resource.value(prov.wasGeneratedBy)
    gen.add(prov.used, URIRef('file://'+os.path.join(cwd,inputfile)))

    for entry, uri in tab_config.items():
        res = setl_graph.resource(uri)
        sheet = infosheet_dict[entry]
        gen = res.value(prov.wasGeneratedBy)
        if sheet.startswith('#'):
            res.add(rdflib.RDF.type, setl.Excel)
            res.add(setl.sheetname, rdflib.Literal(sheet[1:]))
            gen.add(prov.used, URIRef('file://'+os.path.join(cwd,inputfile)))
        else:
            res.add(rdflib.RDF.type, csvw.Table)
            gen.add(prov.used, URIRef(sheet))
    context = {
        "@base" :  "http://purl.org/twc/ctxid/",
        "sio" :     "http://semanticscience.org/resource/",
        "chear" :   "http://hadatac.org/ont/chear#",
        "skos" :    "http://www.w3.org/2004/02/skos/core#",
        "prov" :    "http://www.w3.org/ns/prov#",
        "dc"   :    "http://purl.org/dc/terms/",
        "cmo"  :    "http://purl.obolibrary.org/obo/CMO_",
        "doid" : "http://purl.obolibrary.org/obo/DOID_",
        "owl": "http://www.w3.org/2002/07/owl#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "rdfs" :    "http://www.w3.org/2000/01/rdf-schema#",
        "chebi" :   "http://purl.obolibrary.org/obo/CHEBI_",
        "stato" :   "http://purl.obolibrary.org/obo/STATO_",
        "obo" :   "http://purl.obolibrary.org/obo/",
        "pubchem" : "http://rdf.ncbi.nlm.nih.gov/pubchem/compound/",
        "dc"   :    "http://purl.org/dc/terms/",
        "hasco" : "http://hadatac.org/ont/hasco#",
        "vstoi" : "http://hadatac.org/ont/vstoi#",
        "hasneto" : "http://hadatac.org/ont/hasneto#",
        "uberon" : "http://purl.obolibrary.org/obo/UBERON_",
        "prv" : "http://hadatac.org/ont/prov#"
    }

    namespaces = load_namespaces()
    context.update(namespaces)
    setl_graph.add((sddns.metadata_transform,setl.hasContext,Literal(json.dumps(context))))

    setl_graph.add((sddns.namespaces,prov.value,
                    Literal("result = %s" % json.dumps(context))))

    resources = setlr._setl(setl_graph)

    ont = resources[sddns.metadata]

    prefix = "http://purl.org/twc/ctxid/"

    mappings = {}

    for cls, identifier in ont.query('''select ?cls ?identifier where {
        ?cls a owl:Class; dc:identifier ?identifier.
    }''', initNs= {"owl":rdflib.OWL, "dc": dc}):
        if prefix in str(cls):
            id = cls.replace(prefix,'')
            integer_id = int(id,16)
            ont.add((cls, skos.notation, rdflib.Literal(integer_id)))
            column, code = identifier.split('||||')
            print("Mapping (%s, %s) => %s"%(column, code, cls))
            mappings[(column, code)] = "ctxid:"+id
    with open(ontology,'wb') as o:
        ont.serialize(o, format="turtle")

    codebook = wb[infosheet_dict['Codebook'][1:]]

    header = None
    code_col = None
    class_col = None
    column_col = None
    for row in codebook.rows:
        if header is None:
            header = row
            for cell in header:
                if cell.value == "Code":
                    code_col = cell.column-1
                if cell.value == "Class":
                    class_col = cell.column-1
                if cell.value == "Column":
                    column_col = cell.column-1
            print('Found Column Headers: Code==%s Class==%s Column=%s'%(code_col,class_col,column_col))
            continue
        if (row[column_col].value == None): continue
        column = str(row[column_col].value)
        code = str(row[code_col].value)
        if (column, code) in mappings:
            print("%s.%s = %s"%(column, code, mappings[(column, code)]))
            row[class_col].value = mappings[(column, code)]

    wb.save(outputfile)
