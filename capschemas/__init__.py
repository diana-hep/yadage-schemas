import json
import os
import jsonschema
import jsonref
import requests
import yaml
import urllib2
import logging
from jsonschema import Draft4Validator, validators
import pkg_resources
log = logging.getLogger(__name__)

schemadir = pkg_resources.resource_filename('capschemas','')

def extend_with_default(validator_class):
    validate_properties = validator_class.VALIDATORS["properties"]
    
    def set_defaults(validator, properties, instance, schema):
        if schema.get('title',None)=='Yadage Stage':
            if type(instance['dependencies'])==list:
                log.debug('dependencies provided as list, assume jsonpath_ready predicate')
                instance['dependencies'] = {
                    "dependency_type" : "jsonpath_ready",
                    "expressions": instance["dependencies"]
                    }


        for prop, subschema in properties.iteritems():
            if "default" in subschema:
                instance.setdefault(prop, subschema["default"])
                
        for error in validate_properties(
            validator, properties, instance, schema,
        ):
            yield error
            
    return validators.extend(
        validator_class, {"properties" : set_defaults},
    )

DefaultValidatingDraft4Validator = extend_with_default(Draft4Validator)

def loader(toplevel):
    base_uri = None
    if toplevel.startswith('from-github'):
        within = toplevel.split('/',1)[-1]
        base_uri = 'https://raw.githubusercontent.com/lukasheinrich/yadage-workflows/master/{}'.format(within)
    elif toplevel.startswith('http'):
        base_uri = toplevel
    else:
        base_uri = 'file://' + os.path.abspath(toplevel) + '/'
    
    if not base_uri.endswith('/'):
        base_uri = base_uri + '/'
    
    def yamlloader(uri):
        try:
            log.debug('trying to get uri %s',uri)
            data = requests.get(uri).content
            return yaml.load(data)
        except:
            try:
                data = urllib2.urlopen(uri).read()
                return yaml.load(data)
            except:
                log.exception('loading error: cannot find URI %s',uri)
                raise RuntimeError
    def load(uri):
        full_uri = '{}/{}'.format(base_uri,uri)
        log.debug('trying to load rel: %s full uri: %s base %s',uri,full_uri,base_uri)
        return jsonref.load_uri(full_uri, base_uri = base_uri, loader = yamlloader)
    return load

def validator(schema_name,schemadir):
    schemabase = None
    if schemadir is None:
        schemabase = capschemas.schemadir
    if schemadir=='from-github':
        schemabase = 'https://raw.githubusercontent.com/lukasheinrich/cap-schemas/master/schemas'
    else:
        schemabase = 'file://'+os.path.abspath(schemadir)

    abspath = '{}/{}.json'.format(schemabase,schema_name)
    this_base_uri = abspath.rsplit('/',1)[0]+'/'

    schema   = json.loads(urllib2.urlopen(abspath).read())
    resolver = jsonschema.RefResolver(this_base_uri, schema)
    return DefaultValidatingDraft4Validator(schema, resolver = resolver)

def load(source, toplevel, schema_name, schemadir = None, validate = True):
    load = loader(toplevel)
    data = load(source)
    if validate:
        validator(schema_name,schemadir).validate(data)
    return data