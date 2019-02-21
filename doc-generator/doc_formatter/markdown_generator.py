# Copyright Notice:
# Copyright 2016, 2017, 2018 Distributed Management Task Force, Inc. All rights reserved.
# License: BSD 3-Clause License. For full text see link: https://github.com/DMTF/Redfish-Tools/blob/master/LICENSE.md

"""
File : markdown_generator.py

Brief : This file contains definitions for the MarkdownGenerator class.

Initial author: Second Rise LLC.
"""

import copy
import warnings
from doc_gen_util import DocGenUtilities
from . import DocFormatter
from format_utils import FormatUtils

# Format user warnings simply
def simple_warning_format(message, category, filename, lineno, file=None, line=None):
    """ a basic format for warnings from this program """
    return '  Warning: %s (%s:%s)' % (message, filename, lineno) + "\n"

warnings.formatwarning = simple_warning_format


class MarkdownGenerator(DocFormatter):
    """Provides methods for generating markdown from Redfish schemas.

    Markdown is targeted to the Slate documentation tool: https://github.com/lord/slate
    """


    def __init__(self, property_data, traverser, config, level=0):
        super(MarkdownGenerator, self).__init__(property_data, traverser, config, level)
        self.separators = {
            'inline': ', ',
            'linebreak': '\n',
            'pattern': ', '
            }
        self.formatter = FormatUtils()


    def format_property_row(self, schema_ref, prop_name, prop_info, prop_path=[], in_array=False):
        """Format information for a single property.

        Returns an object with 'row', 'details', 'action_details', and 'profile_conditional_details':

        'row': content for the main table being generated.
        'details': content for the Property Details section.
        'action_details': content for the Actions section.
        'profile_conditional_details': populated only in profile_mode, formatted conditional details

        This may include embedded objects with their own properties.
        """

        traverser = self.traverser
        formatted = []     # The row itself

        current_depth = len(prop_path)
        if in_array:
            current_depth = current_depth -1

        # strip_top_object is used for fragments, to allow output of just the properties
        # without the enclosing object:
        if self.config.get('strip_top_object') and current_depth > 0:
            indentation_string = '&nbsp;' * 6 * (current_depth -1)
        else:
            indentation_string = '&nbsp;' * 6 * current_depth

        # If prop_path starts with Actions and is more than 1 deep, we are outputting for an Action Details
        # section and should dial back the indentation by one level.
        if len(prop_path) > 1 and prop_path[0] == 'Actions':
            indentation_string = '&nbsp;' * 6 * (current_depth -1)

        collapse_array = False # Should we collapse a list description into one row? For lists of simple types
        has_enum = False

        if current_depth < self.current_depth:
            for i in range(current_depth, self.current_depth):
                if i in self.current_version:
                    del self.current_version[i]
        self.current_depth = current_depth
        parent_depth = current_depth - 1

        if isinstance(prop_info, list):
            meta = prop_info[0].get('_doc_generator_meta')
            has_enum = 'enum' in prop_info[0]
        elif isinstance(prop_info, dict):
            meta = prop_info.get('_doc_generator_meta')
            has_enum = 'enum' in prop_info
        if not meta:
            meta = {}

        # We want to modify a local copy of meta, deleting redundant version info
        meta = copy.deepcopy(meta)

        if prop_name:
            name_and_version = self.formatter.bold(self.escape_for_markdown(prop_name,
                                                                  self.config.get('escape_chars', [])))
        else:
            name_and_version = ''

        deprecated_descr = None

        version = meta.get('version')
        self.current_version[current_depth] = version

        # Don't display version if there is a parent version and this is not newer:
        if self.current_version.get(parent_depth) and version:
            version = meta.get('version')
            if DocGenUtilities.compare_versions(version, self.current_version.get(parent_depth)) <= 0:
                del meta['version']

        if meta.get('version', '1.0.0') != '1.0.0':
            version_display = self.truncate_version(meta['version'], 2) + '+'
            if 'version_deprecated' in meta:
                deprecated_display = self.truncate_version(meta['version_deprecated'], 2)
                name_and_version += ' ' + self.formatter.italic('(v' + version_display +
                                                      ', deprecated v' + deprecated_display +  ')')
                deprecated_descr = ("Deprecated v" + deprecated_display + '+. ' +
                                    self.escape_for_markdown(meta['version_deprecated_explanation'], self.config.get('escape_chars', [])))
            else:
                name_and_version += ' ' + self.formatter.italic('(v' + version_display + ')')
        elif 'version_deprecated' in meta:
            deprecated_display = self.truncate_version(meta['version_deprecated'], 2)
            name_and_version += ' ' + self.formatter.italic('(deprecated v' + deprecated_display +  ')')
            deprecated_descr =  ("Deprecated v" + deprecated_display + '+. ' +
                                 self.escape_for_markdown(meta['version_deprecated_explanation'],
                                                          self.config.get('escape_chars', [])))

        formatted_details = self.parse_property_info(schema_ref, prop_name, prop_info, prop_path,
                                                     meta.get('within_action'))

        if formatted_details.get('promote_me'):
            return({'row': '\n'.join(formatted_details['item_description']), 'details':formatted_details['prop_details'],
                    'action_details':formatted_details.get('action_details')})

        if self.config.get('strip_top_object') and current_depth == 0:
            # In this case, we're done for this bit of documentation, and we just want the properties of this object.
            formatted.append('\n'.join(formatted_details['object_description']))
            return({'row': '\n'.join(formatted), 'details':formatted_details['prop_details'],
                    'action_details':formatted_details.get('action_details'),
                    'profile_conditional_details': formatted_details.get('profile_conditional_details')})


        # Eliminate dups in these these properties and join with a delimiter:
        props = {
            'prop_type': self.separators['inline'],
            'descr': self.separators['linebreak'],
            'object_description': self.separators['linebreak'],
            'item_description': self.separators['linebreak']
            }

        for property_name, delim in props.items():
            if isinstance(formatted_details[property_name], list):
                property_values = []
                self.append_unique_values(formatted_details[property_name], property_values)
                formatted_details[property_name] = delim.join(property_values)

        if formatted_details['prop_is_object'] and not in_array:
            if formatted_details['object_description'] == '':
                name_and_version += ' {}'
            else:
                name_and_version += ' {'

        if formatted_details['prop_is_array']:
            if formatted_details['item_description'] == '':
                if formatted_details['array_of_objects']:
                    name_and_version += ' [ {} ]'
                else:
                    name_and_version += ' [ ]'
            else:
                if formatted_details['array_of_objects']:
                    name_and_version += ' [ {'
                else:
                    collapse_array = True
                    name_and_version += ' [ ]'
        elif in_array:
            if formatted_details['prop_is_object']:
                name_and_version += ' [ { } ]'
            else:
                name_and_version += ' [ ]'

        if formatted_details['descr'] is None:
            formatted_details['descr'] = ''

        if formatted_details['profile_purpose']:
            if formatted_details['descr']:
                formatted_details['descr'] += ' '
            formatted_details['descr'] += self.formatter.bold(formatted_details['profile_purpose'])

        if formatted_details['descr'] is None:
            formatted_details['descr'] = ''

        if formatted_details['profile_purpose']:
            if formatted_details['descr']:
                formatted_details['descr'] += ' '
            formatted_details['descr'] += self.formatter.bold(formatted_details['profile_purpose'])

        if formatted_details['add_link_text']:
            if formatted_details['descr']:
                formatted_details['descr'] += ' '
            formatted_details['descr'] += formatted_details['add_link_text']

        # Append reference info to descriptions, if appropriate:
        if not formatted_details.get('fulldescription_override'):
            if formatted_details['has_direct_prop_details'] and not formatted_details['has_action_details']:
                # If there are prop_details (enum details), add a note to the description:
                if has_enum:
                    text_descr = 'See ' + prop_name + ' in Property Details, below, for the possible values of this property.'
                else:
                    text_descr = 'See Property Details, below, for more information about this property.'
                formatted_details['descr'] += ' ' + self.formatter.italic(text_descr)

            if formatted_details['has_action_details']:
                text_descr = 'For more information, see the Action Details section below.'
                formatted_details['descr'] += ' ' + self.formatter.italic(text_descr)

        if deprecated_descr:
            formatted_details['descr'] += ' ' + self.formatter.italic(deprecated_descr)

        prop_type = formatted_details['prop_type']
        if has_enum:
            prop_type += '<br>(enum)'

        if formatted_details['prop_units']:
            prop_type += '<br>(' + formatted_details['prop_units'] + ')'

        if in_array:
            prop_type = 'array (' + prop_type + ')'

        if collapse_array:
            item_list = formatted_details['item_list']
            if len(item_list):
                if isinstance(item_list, list):
                    item_list = ', '.join(item_list)
                prop_type += ' (' + item_list + ')'

        prop_access = ''
        if not meta.get('is_pattern') and not formatted_details['prop_is_object']:
            if formatted_details['read_only']:
                prop_access = 'read-only'
            else:
                prop_access = 'read-write'

        if formatted_details['prop_required_on_create']:
            prop_access += ' required on create'
        elif formatted_details['prop_required'] or formatted_details['required_parameter']:
            prop_access += ' required'

        if formatted_details['nullable']:
            prop_access += '<br>(null)'

        # If profile reqs are present, massage them:
        profile_access = self.format_base_profile_access(formatted_details)

        if self.config.get('profile_mode'):
            if profile_access:
                prop_type += '<br><br>' + self.formatter.italic(profile_access)
        elif prop_access:
            prop_type += '<br><br>' + self.formatter.italic(prop_access)


        row = []
        row.append(indentation_string + name_and_version)
        row.append(prop_type)
        row.append(formatted_details['descr'])

        formatted.append('| ' + ' | '.join(row) + ' |')

        if len(formatted_details['object_description']) > 0:
            formatted.append(formatted_details['object_description'])
            formatted.append('| ' + indentation_string + '} |   |   |')

        if not collapse_array and len(formatted_details['item_description']) > 0:
            formatted.append(formatted_details['item_description'])
            if formatted_details['array_of_objects']:
                formatted.append('| ' + indentation_string + '} ] |   |   |')
            else:
                formatted.append('| ' + indentation_string + '] |   |   |')

        return({'row': '\n'.join(formatted), 'details':formatted_details['prop_details'],
                'action_details':formatted_details.get('action_details'),
                'profile_conditional_details': formatted_details.get('profile_conditional_details')})


    def format_property_details(self, prop_name, prop_type, prop_description, enum, enum_details,
                                supplemental_details, meta, anchor=None, profile=None):
        """Generate a formatted table of enum information for inclusion in Property Details."""

        contents = []
        contents.append(self.formatter.head_three(prop_name + ':', self.level))

        parent_version = meta.get('version')
        enum_meta = meta.get('enum', {})

        # Are we in profile mode? If so, consult the profile passed in for this property.
        # For Action Parameters, look for ParameterValues/RecommendedValues; for
        # Property enums, look for MinSupportValues/RecommendedValues.
        profile_mode = self.config.get('profile_mode')
        if profile_mode:
            if profile is None:
                profile = {}

            profile_values = profile.get('Values', [])
            profile_min_support_values = profile.get('MinSupportValues', [])
            profile_parameter_values = profile.get('ParameterValues', [])
            profile_recommended_values = profile.get('RecommendedValues', [])

            profile_all_values = (profile_values + profile_min_support_values + profile_parameter_values
                                  + profile_recommended_values)

        if prop_description:
            contents.append(self.formatter.para(self.escape_for_markdown(prop_description, self.config.get('escape_chars', []))))

        if isinstance(prop_type, list):
            prop_type = ', '.join(prop_type)

        if supplemental_details:
            contents.append('\n' + supplemental_details + '\n')

        if enum_details:
            if profile_mode:
                contents.append('| ' + prop_type + ' | Description | Profile Specifies |')
                contents.append('| --- | --- | --- |')
            else:
                contents.append('| ' + prop_type + ' | Description |')
                contents.append('| --- | --- |')
            enum.sort(key=str.lower)
            for enum_item in enum:
                enum_name = enum_item
                enum_item_meta = enum_meta.get(enum_item, {})
                version_display = None
                deprecated_descr = None
                if 'version' in enum_item_meta:
                    version = enum_item_meta['version']
                    if not parent_version or DocGenUtilities.compare_versions(version, parent_version) > 0:
                        version_display = self.truncate_version(version, 2) + '+'
                if version_display:
                    if 'version_deprecated' in enum_item_meta:
                        version_depr = enum_item_meta['version_deprecated']
                        deprecated_display = self.truncate_version(version_depr, 2)
                        enum_name += ' ' + self.formatter.italic('(v' + version_display + ', deprecated v' + deprecated_display + ')')
                        if enum_item_meta.get('version_deprecated_explanation'):
                            deprecated_descr = ("Deprecated v" + deprecated_display + '+. ' +
                                                enum_item_meta['version_deprecated_explanation'])
                    else:
                        enum_name += ' ' + self.formatter.italic('(v' + version_display + ')')
                else:
                    if 'version_deprecated' in enum_item_meta:
                        version_depr = enum_item_meta['version_deprecated']
                        deprecated_display = self.truncate_version(version_depr, 2)
                        enum_name += ' ' + self.formatter.italic('(deprecated v' + deprecated_display + ')')
                        if enum_item_meta.get('version_deprecated_explanation'):
                            deprecated_descr = ("Deprecated v" + deprecated_display + '+. ' +
                                                enum_item_meta['version_deprecated_explanation'])
                descr = enum_details.get(enum_item, '')
                if deprecated_descr:
                    if descr:
                        descr += ' ' + self.formatter.italic(deprecated_descr)
                    else:
                        descr = self.formatter.italic(deprecated_descr)

                if profile_mode:
                    profile_spec = ''
                    if enum_name in profile_values:
                        profile_spec = 'Required'
                    elif enum_name in profile_min_support_values:
                        profile_spec = 'Required'
                    elif enum_name in profile_parameter_values:
                        profile_spec = 'Required'
                    elif enum_name in profile_recommended_values:
                        profile_spec = 'Recommended'
                    contents.append('| ' + enum_name + ' | ' + descr + ' | ' + profile_spec + ' |')
                else:
                    contents.append('| ' + enum_name + ' | ' + descr + ' |')

        elif enum:
            if profile_mode:
                contents.append('| ' + prop_type + ' | Profile Specifies |')
                contents.append('| --- | --- |')
            else:
                contents.append('| ' + prop_type + ' |')
                contents.append('| --- |')
            for enum_item in enum:
                enum_name = enum_item
                enum_item_meta = enum_meta.get(enum_item, {})
                version_display = None

                if 'version' in enum_item_meta:
                    version = enum_item_meta['version']
                    if not parent_version or DocGenUtilities.compare_versions(version, parent_version) > 0:
                        version_display = self.truncate_version(version, 2) + '+'
                if version_display:
                    if 'version_deprecated' in enum_item_meta:
                        version_depr = enum_item_meta['version_deprecated']
                        deprecated_display = self.truncate_version(version_depr, 2)
                        enum_name += ' ' + self.formatter.italic('(v' + version_display + ', deprecated v' + deprecated_display + ')')
                        if enum_item_meta.get('version_deprecated_explanation'):
                            deprecated_descr = ('Deprecated v' + deprecated_display + '+. ' +
                                                enum_item_meta['version_deprecated_explanation'])
                    else:
                        enum_name += ' ' + self.formatter.italic('(v' + version_display + ')')
                else:
                    if 'version_deprecated' in enum_item_meta:
                        version_depr = enum_item_meta['version_deprecated']
                        deprecated_display = self.truncate_version(version_depr, 2)
                        enum_name += ' ' + self.formatter.italic('(deprecated v' + deprecated_display + ')')
                        if enum_item_meta.get('version_deprecated_explanation'):
                            enum_name += ' ' + self.formatter.italic('Deprecated v' + deprecated_display + '+. ' +
                                                           enum_item_meta['version_deprecated_explanation'])

                if profile_mode:
                    profile_spec = ''
                    if enum_name in profile_values:
                        profile_spec = 'Required'
                    elif enum_name in profile_min_support_values:
                        profile_spec = 'Required'
                    elif enum_name in profile_parameter_values:
                        profile_spec = 'Required'
                    elif enum_name in profile_recommended_values:
                        profile_spec = 'Recommended'

                    contents.append('| ' + enum_name + ' | ' + profile_spec + ' |')
                else:
                    contents.append('| ' + enum_name + ' | ')

        return '\n'.join(contents) + '\n'


    def format_action_details(self, prop_name, action_details):
        """Generate a formatted Actions section from supplemental markup."""

        contents = []
        contents.append(self.formatter.head_three(action_details.get('action_name', prop_name), self.level))
        if action_details.get('text'):
            contents.append(action_details.get('text'))
        if action_details.get('example'):
            example = '```json\n' + action_details['example'] + '\n```\n'
            contents.append('Example Action POST:\n')
            contents.append(example)

        return '\n'.join(contents) + '\n'


    def format_action_parameters(self, schema_ref, prop_name, prop_descr, action_parameters):
        """Generate a formatted Actions section from parameter data. """

        formatted = []

        if prop_name.startswith('#'): # expected
            prop_name_parts = prop_name.split('.')
            prop_name = prop_name_parts[-1]

        formatted.append(self.formatter.head_four(prop_name, self.level))
        formatted.append(self.formatter.para(prop_descr))

        if action_parameters:
            rows = []
            # Table start:
            rows.append("|     |     |     |")
            rows.append("| --- | --- | --- |")

            # Add a "start object" row for this parameter:
            rows.append('| ' + ' | '.join(['{', ' ',' ',' ']) + ' |')
            param_names = [x for x in action_parameters.keys()]
            param_names.sort(key=str.lower)
            for param_name in param_names:
                formatted_parameters = self.format_property_row(schema_ref, param_name, action_parameters[param_name], ['Actions', prop_name])
                rows.append(formatted_parameters.get('row'))

            # Add a closing } row:
            rows.append('| ' + ' | '.join(['}', ' ',' ',' ']) + ' |')

            formatted.append(self.formatter.para('The following table shows the parameters for the action which are included in the POST body to the URI shown in the "target" property of the Action.'))

            formatted.append('\n'.join(rows))

        else:
            formatted.append(self.formatter.para("(This action takes no parameters.)"))

        return "\n".join(formatted)


    def _format_profile_access(self, read_only=False, read_req=None, write_req=None, min_count=None):
        """Common formatting logic for profile_access column"""

        profile_access = ''
        if not self.config['profile_mode']:
            return profile_access

        # Each requirement  may be Mandatory, Recommended, IfImplemented, Conditional, or (None)
        if not read_req:
            read_req = 'Mandatory' # This is the default if nothing is specified.
        if read_only:
            profile_access = self.formatter.nobr(self.text_map(read_req)) + ' (Read-only)'
        elif read_req == write_req:
            profile_access = self.formatter.nobr(self.text_map(read_req)) + ' (Read/Write)'
        elif not write_req:
            profile_access = self.formatter.nobr(self.text_map(read_req)) + ' (Read)'
        else:
            # Presumably Read is Mandatory and Write is Recommended; nothing else makes sense.
            profile_access = (self.formatter.nobr(self.text_map(read_req)) + ' (Read),' +
                              self.formatter.nobr(self.text_map(write_req)) + ' (Read/Write)')

        if min_count:
            if profile_access:
                profile_access += ", "
            profile_access += self.formatter.nobr("Minimum " + str(min_count))

        return profile_access


    def link_to_own_schema(self, schema_ref, schema_full_uri):
        """Format a reference to a schema."""
        result = super().link_to_own_schema(schema_ref, schema_full_uri)
        return self.formatter.italic(result)


    def link_to_outside_schema(self, schema_full_uri):
        """Format a reference to a schema_uri, which should be a valid URI"""
        return self.formatter.italic('['+ schema_full_uri + '](' + schema_full_uri + ')')


    def emit(self):
        """ Output contents thus far """

        contents = []

        for section in self.sections:
            contents.append(section.get('heading'))
            if section.get('description'):
                contents.append(section['description'])
            if section.get('uris'):
                contents.append(section['uris'])
            if section.get('json_payload'):
                contents.append(section['json_payload'])
            # something is awry if there are no properties, but ...
            if section.get('properties'):
                contents.append('|     |     |     |')
                contents.append('| --- | --- | --- |')
                contents.append('\n'.join(section['properties']))

            if section.get('profile_conditional_details'):
                # sort them now; these can be sub-properties so may not be in alpha order.
                conditional_details = '\n'.join(sorted(section['profile_conditional_details'], key=str.lower))
                contents.append('\n' + self.formatter.head_two('Conditional Requirements', self.level))
                contents.append(conditional_details)

            if len(section.get('action_details', [])):
                contents.append('\n' + self.formatter.head_two('Action Details', self.level))
                contents.append('\n\n'.join(section.get('action_details')))
            if section.get('property_details'):
                contents.append('\n' + self.formatter.head_two('Property Details', self.level))
                contents.append('\n'.join(section['property_details']))

        self.sections = []

        # Profile output may include registry sections
        for section in self.registry_sections:
            contents.append(section.get('heading'))
            contents.append(section.get('requirement'))
            if section.get('description'):
                contents.append(self.formatter.para(section['description']))
            if section.get('messages'):
                contents.append(self.formatter.head_two('Messages', self.level))
                message_rows = [self.formatter.make_row(x) for x in section['messages']]
                header_cells = ['', 'Requirement']
                if self.config.get('profile_mode') != 'terse':
                    header_cells.append('Description')
                header_row = self.formatter.make_row(header_cells)
                contents.append(self.formatter.make_table(message_rows, [header_row], 'messages'))
                contents.append('\n')

        return '\n'.join(contents)


    def output_document(self):
        """Return full contents of document"""
        body = self.emit()
        common_properties = self.generate_common_properties_doc()

        supplemental = self.config.get('supplemental', {})

        if 'Title' in supplemental:
            doc_title = supplemental['Title']
        else:
            doc_title = 'Schema Documentation'

        prelude = "---\ntitle: " + doc_title + """

search: true
---
"""

        intro = supplemental.get('Introduction')
        if intro:
            intro = self.process_intro(intro)
            prelude += '\n' + intro + '\n'

        contents = [prelude, body]
        if 'Postscript' in supplemental:
            contents.append('\n' + supplemental['Postscript'])

        output = '\n'.join(contents)
        if '[insert_common_objects]' in output:
            output = output.replace('[insert_common_objects]', common_properties, 1)

        if '[insert_collections]' in output:
            collections_doc = self.generate_collections_doc()
            output = output.replace('[insert_collections]', collections_doc, 1)

        # Replace pagebreak markers with HTML pagebreak markup
        output = output.replace('~pagebreak~', '<p style="page-break-before: always"></p>')

        return output


    def process_intro(self, intro_blob):
        """ Process the intro text, generating and inserting any schema fragments """
        parts = []
        intro = []
        part_text = []

        fragment_config = {
            'output_format': 'markdown',
            'normative': self.config.get('normative'),
            'cwd': self.config.get('cwd'),
            'schema_supplement': {},
            'supplemental': {},
            'excluded_annotations': [],
            'excluded_annotations_by_match': [],
            'excluded_properties': [],
            'excluded_by_match': [],
            'excluded_schemas': [],
            'excluded_schemas_by_match': [],
            'escape_chars': [],
            'uri_replacements': {},
            'units_translation': self.config.get('units_translation'),
            'profile': self.config.get('profile'),
            'profile_mode': self.config.get('profile_mode'),
            'profile_resources': self.config.get('profile_resources', {}),
            'wants_common_objects': self.config.get('wants_common_objects'),
            }

        for line in intro_blob.splitlines():
            if line.startswith('#include_fragment'):
                if len(part_text):
                    parts.append({'type': 'markdown', 'content': '\n'.join(part_text)})
                    part_text = []
                    fragment_id = line[17:].strip()
                    fragment_content = self.generate_fragment_doc(fragment_id, fragment_config)
                    parts.append({'type': 'fragment', 'content': fragment_content})
            else:
                part_text.append(line)

        if len(part_text):
            parts.append({'type': 'markdown', 'content': '\n'.join(part_text)})

        for part in parts:
            if part['type'] == 'markdown':
                intro.append(part['content'])
            elif part['type'] == 'fragment':
                intro.append(part['content'])
        return '\n'.join(intro)


    def add_section(self, text, link_id=False):
        """ Add a top-level heading """
        self.this_section = {'head': text,
                             'heading': '\n' + self.formatter.head_one(text, self.level),
                             'properties': [],
                             'property_details': []
                            }
        self.sections.append(self.this_section)


    def add_description(self, text):
        """ Add the schema description """
        self.this_section['description'] = text + '\n'


    def add_uris(self, uris):
        """ Add the URIs (which should be a list) """
        uri_block = "**URIs**:\n"
        for uri in sorted(uris, key=str.lower):
            uri_block += "\n" + self.format_uri(uri)

        self.this_section['uris'] = uri_block + "\n"


    def add_json_payload(self, json_payload):
        """ Add a JSON payload for the current section """
        if json_payload:
            self.this_section['json_payload'] = '\n' + json_payload + '\n'
        else:
            self.this_section['json_payload'] = None


    def add_property_row(self, formatted_text):
        """Add a row (or group of rows) for an individual property in the current section/schema.

        formatted_row should be a chunk of text already formatted for output"""
        self.this_section['properties'].append(formatted_text)


    def add_property_details(self, formatted_details):
        """Add a chunk of property details information for the current section/schema."""
        self.this_section['property_details'].append(formatted_details)


    def add_registry_reqs(self, registry_reqs):
        """Add registry messages. registry_reqs includes profile annotations."""

        terse_mode = self.config.get('profile_mode') == 'terse'

        reg_names = [x for x in registry_reqs.keys()]
        reg_names.sort(key=str.lower)
        for reg_name in reg_names:
            reg = registry_reqs[reg_name]
            this_section = {
                'head': reg_name,
                'description': reg.get('Description', ''),
                'messages': []
                }
            heading = reg_name + ' Registry v' + reg['minversion']  + '+'
            if reg.get('current_release', reg['minversion']) != reg['minversion']:
                heading += ' (current release: v' + reg['current_release'] + ')'

            this_section['heading'] = self.formatter.head_one(heading, self.level)
            this_section['requirement'] = 'Requirement: ' + reg.get('profile_requirement', '')

            msgs = reg.get('Messages', {})
            msg_keys = [x for x in msgs.keys()]
            msg_keys.sort(key=str.lower)

            for msg in msg_keys:
                this_msg = msgs[msg]
                if terse_mode and not this_msg.get('profile_requirement'):
                    continue
                msg_row = [msg, this_msg.get('profile_requirement', '')]
                if not terse_mode:
                    msg_row.append(this_msg.get('Description', ''))
                this_section['messages'].append(msg_row)

            self.registry_sections.append(this_section)


    @staticmethod
    def escape_for_markdown(text, chars):
        """Escape selected characters in text to prevent auto-formatting in markdown."""
        for char in chars:
            text = text.replace(char, '\\' + char)
        return text
