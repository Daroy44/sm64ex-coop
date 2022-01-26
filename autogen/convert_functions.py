import os
import re

rejects = ""
integer_types = ["u8", "u16", "u32", "u64", "s8", "s16", "s32", "s64", "int"]
number_types = ["f32", "float"]
cobject_types = ["struct MarioState*", "struct Object*", "struct Surface*"]
cobject_lot_types = ["LOT_MARIO_STATE", "LOT_OBJECT", "LOT_SURFACE"]
param_override_build = {}

###########################################################

template = """/* THIS FILE IS AUTOGENERATED */
/* SHOULD NOT BE MANUALLY CHANGED */

#include "smlua.h"

#include "game/level_update.h"
#include "game/area.h"
#include "game/mario.h"
#include "game/mario_step.h"
#include "game/mario_actions_stationary.h"
#include "audio/external.h"
#include "object_fields.h"
#include "engine/math_util.h"
#include "engine/surface_collision.h"

$[FUNCTIONS]

void smlua_bind_functions_autogen(void) {
    lua_State* L = gLuaState;
$[BINDS]
}
"""

###########################################################

param_vec3f_before_call = """
    f32* $[IDENTIFIER] = smlua_get_vec3f_from_buffer();
    $[IDENTIFIER][0] = smlua_get_number_field($[INDEX], "x");
    if (!gSmLuaConvertSuccess) { return 0; }
    $[IDENTIFIER][1] = smlua_get_number_field($[INDEX], "y");
    if (!gSmLuaConvertSuccess) { return 0; }
    $[IDENTIFIER][2] = smlua_get_number_field($[INDEX], "z");
"""

param_vec3f_after_call = """
    smlua_push_number_field($[INDEX], "x", $[IDENTIFIER][0]);
    smlua_push_number_field($[INDEX], "y", $[IDENTIFIER][1]);
    smlua_push_number_field($[INDEX], "z", $[IDENTIFIER][2]);
"""

param_override_build['Vec3f'] = {
    'before': param_vec3f_before_call,
    'after': param_vec3f_after_call
}

param_vec3s_before_call = """
    s16* $[IDENTIFIER] = smlua_get_vec3s_from_buffer();
    $[IDENTIFIER][0] = smlua_get_integer_field($[INDEX], "x");
    if (!gSmLuaConvertSuccess) { return 0; }
    $[IDENTIFIER][1] = smlua_get_integer_field($[INDEX], "y");
    if (!gSmLuaConvertSuccess) { return 0; }
    $[IDENTIFIER][2] = smlua_get_integer_field($[INDEX], "z");
"""

param_vec3s_after_call = """
    smlua_push_integer_field($[INDEX], "x", $[IDENTIFIER][0]);
    smlua_push_integer_field($[INDEX], "y", $[IDENTIFIER][1]);
    smlua_push_integer_field($[INDEX], "z", $[IDENTIFIER][2]);
"""

param_override_build['Vec3s'] = {
    'before': param_vec3s_before_call,
    'after': param_vec3s_after_call
}

###########################################################

built_functions = ""
built_binds = ""

#######

do_extern = False
header_h = ""

functions = []

def reject_line(line):
    if len(line) == 0:
        return True
    if '(' not in line:
        return True
    if ')' not in line:
        return True
    if ';' not in line:
        return True

def normalize_type(t):
    t = t.strip()
    if ' ' in t:
        parts = t.split(' ', 1)
        t = parts[0] + ' ' + parts[1].replace(' ', '')
    return t

def gen_comment_header(f):
    comment_h = "// " + f + " //"
    comment_l = "/" * len(comment_h)
    s = ""
    s += "  " + comment_l + "\n"
    s += " "  + comment_h + "\n"
    s += ""   + comment_l + "\n"
    s += "\n"
    return s

def process_line(line):
    function = {}

    line = line.strip()
    function['line'] = line

    line = line.replace('UNUSED', '')

    match = re.search('[a-zA-Z0-9_]+\(', line)
    function['type'] = normalize_type(line[0:match.span()[0]])
    function['identifier'] = match.group()[0:-1]

    function['params'] = []
    params_str = line.split('(', 1)[1].rsplit(')', 1)[0].strip()
    if len(params_str) == 0 or params_str == 'void':
        pass
    else:
        param_index = 0
        for param_str in params_str.split(','):
            param = {}
            param_str = param_str.strip()
            if param_str.endswith('*') or ' ' not in param_str:
                param['type'] = normalize_type(param_str)
                param['identifier'] = 'arg%d' % param_index
            else:
                match = re.search('[a-zA-Z0-9_]+$', param_str)
                param['type'] = normalize_type(param_str[0:match.span()[0]])
                param['identifier'] = match.group()
            function['params'].append(param)
            param_index += 1

    functions.append(function)

def process_lines(file_str):
    for line in file_str.splitlines():
        if reject_line(line):
            global rejects
            rejects += line + '\n'
            continue
        process_line(line)

def build_param(param, i):
    ptype = param['type']
    pid = param['identifier']

    if ptype in param_override_build:
        return param_override_build[ptype]['before'].replace('$[IDENTIFIER]', str(pid)).replace('$[INDEX]', str(i))
    elif ptype in integer_types:
        return '    %s %s = smlua_to_integer(L, %d);\n' % (ptype, pid, i)
    elif ptype in number_types:
        return '    %s %s = smlua_to_number(L, %d);\n' % (ptype, pid, i)
    elif ptype in cobject_types:
        index = cobject_types.index(ptype)
        return '    %s %s = (%s)smlua_to_cobject(L, %d, %s);\n' % (ptype, pid, ptype, i, cobject_lot_types[index])
    else:
        return '    ' + ptype + ' ' + pid + ' <--- UNIMPLEMENTED' + '\n'

def build_param_after(param, i):
    ptype = param['type']
    pid = param['identifier']

    if ptype in param_override_build:
        return param_override_build[ptype]['after'].replace('$[IDENTIFIER]', str(pid)).replace('$[INDEX]', str(i))
    else:
        return ''

def build_call(function):
    ftype = function['type']
    fid = function['identifier']

    ccall = '%s(%s)' % (fid, ', '.join([x['identifier'] for x in function['params']]))

    if ftype == 'void':
        return '    %s;\n' % ccall

    lfunc = 'UNIMPLEMENTED -->'
    if ftype in integer_types:
        lfunc = 'lua_pushinteger'
    elif ftype in number_types:
        lfunc = 'lua_pushnumber'

    return '    %s(L, %s);\n' % (lfunc, ccall)

def build_function(function):
    if len(function['params']) <= 0:
        s = 'int smlua_func_%s(UNUSED lua_State* L) {\n' % function['identifier']
    else:
        s = 'int smlua_func_%s(lua_State* L) {\n' % function['identifier']

    s += '    if(!smlua_functions_valid_param_count(L, %d)) { return 0; }\n\n' % len(function['params'])

    i = 1
    for param in function['params']:
        s += build_param(param, i)
        s += '    if (!gSmLuaConvertSuccess) { return 0; }\n'
        i += 1
    s += '\n'

    global do_extern
    if do_extern:
        s += '    extern %s\n' % function['line']

    s += build_call(function)

    i = 1
    for param in function['params']:
        s += build_param_after(param, i)
        i += 1
    s += '\n'

    s += '    return 1;\n}\n'

    function['implemented'] = 'UNIMPLEMENTED' not in s
    if 'UNIMPLEMENTED' in s:
        s = "/*\n" + s + "*/\n"

    global built_functions
    built_functions += s + "\n"

def build_functions():
    for function in functions:
        build_function(function)

def build_bind(function):
    s = 'smlua_bind_function(L, "%s", smlua_func_%s);' % (function['identifier'], function['identifier'])
    if function['implemented']:
        s = '    ' + s
    else:
        s = '    //' + s + ' <--- UNIMPLEMENTED'
    global built_binds
    built_binds += s + "\n"

def build_binds(fname):
    global built_binds
    built_binds += "\n    // " + fname.split('/')[-1] + "\n"
    for function in functions:
        build_bind(function)

def process_file(fname):
    functions.clear()
    global do_extern
    do_extern = fname.endswith(".c")
    with open(fname) as file:
        process_lines(file.read())
    build_functions()
    build_binds(fname)

def process_files():
    dir_path = os.path.dirname(os.path.realpath(__file__)) + '/lua_functions/'
    files = os.listdir(dir_path)
    for f in files:
        comment_header = "// " + f + " //"
        comment_line = "/" * len(comment_header)

        global built_functions
        built_functions += gen_comment_header(f)

        process_file(dir_path + f)

def main():
    process_files()
    filename = os.path.dirname(os.path.realpath(__file__)) + '/../src/pc/lua/smlua_functions_autogen.c'
    with open(filename, 'w') as out:
        out.write(template.replace("$[FUNCTIONS]", built_functions).replace("$[BINDS]", built_binds))
    print('REJECTS:')
    print(rejects)

main()
