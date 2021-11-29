#!/usr/bin/env python3

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET

# I want to be able to run this on macOS, too, because that is my
# preferred desktop. (In that case the --isystem option is needed,
# of course.)

if os.name == 'nt':
    winhome = os.environ['USERPROFILE']
else:
    winhome = 'nonexistent'

includedir = winhome + '/AppData/Local/Packages/Microsoft.FlightSimulator_8wekyb3d8bbwe/LocalCache/Packages/Official/OneStore/fs-base-aircraft-common/ModelBehaviorDefs'

# Argument handling

parser = argparse.ArgumentParser()

parser.add_argument('-v', '--verbose', action='store_true', dest='verbose')
parser.add_argument('-I', '--include', action='store', dest='includedir')
parser.add_argument('input')

args = parser.parse_args()

if args.includedir:
    includedir = args.includedir

templates = { }

def verbose(level, string):
    if args.verbose:
        indent = ''
        for i in range(level):
            indent += '  '
        print(indent + string, file=sys.stderr)

def fatal(string):
    print(string, file=sys.stderr)
    exit(1)

def writeelement(elem):
    ET.ElementTree(elem).write(sys.stderr, encoding='Unicode')

def elemtostring(elem):
    result = '<' + elem.tag;
    for i in elem.keys():
        result += ' ' + i + '="' + elem.get(i) + '"'
    result += '>'
    return result

def parse(filename):
    with open(filename, 'r') as f:
        data = f.read()
        data = re.sub(r'#([A-Z0-9_]+)#', r'__HASHSTART__\1__ENDHASH__', data)
        return ET.fromstring(data)
    return None

def removechildren(elem):
    for i in list(elem):
        elem.remove(i)
    if len(list(elem)) != 0:
        fatal('Removing all children of ' + elemtostring(elem) + ' did not work')

def removeattribs(elem):
    keys = elem.keys()
    for i in keys:
        elem.set(i, None)

def shallowcopyelement(elem):
    result = ET.Element(elem.tag, elem.attrib)
    for i in list(elem):
        result.append(i)
    result.text = elem.text
    result.tail = elem.tail
    return result

def elide(elem, tag):
    result = [ ]
    if elem.tag == tag:
        for i in list(elem):
            result.extend(elide(i, tag))
    else:
        kids = []
        for i in list(elem):
            kids.extend(elide(i, tag))
        removechildren(elem)
        for i in kids:
            elem.append(i)
        result = [elem]
    return result

def expandparamname(name, params):
    value = params.get(name)
    if value != None:
        return value
    return name

def expandstring(string, params):
    if string == None:
        return None
    if string.find('__HASHSTART__') == -1:
        return string
    for key, value in params.items():
        string = re.sub('__HASHSTART__' + key + '__ENDHASH__', value, string)
    return string

def expandparameters(elem, params):
    elem.tag = expandstring(elem.tag, params)
    elem.text = expandstring(elem.text, params)
    elem.tail = expandstring(elem.tail, params)
    newattribs = {}
    for key, value in elem.items():
        newvalue = expandstring(value, params)
        newkey = expandstring(key, params)
        newattribs[newkey] = newvalue
    removeattribs(elem)
    for key, value in newattribs.items():
        elem.set(key, value)
    for i in list(elem):
        expandparameters(i, params.copy())
    return elem

def evalrpn(rpn, kind, level, params):
    NUMBER = r'-?\d+(?:\.\d+)?'
    IDENTIFIER = r'[_A-Za-z][_A-Za-z0-9]+'
    tokens = re.findall(NUMBER + '|' + IDENTIFIER + '|' + r'-?\d+(?:\.\d+)?|[_A-Za-z][_A-Za-z0-9]+|\+|-|\*|/', rpn)
    stack = []
    for token in tokens:
        if re.fullmatch(NUMBER, token):
            stack.append(float(token))
        elif re.fullmatch(IDENTIFIER, token):
            match = re.fullmatch('__HASHSTART__(' + IDENTIFIER + ')__ENDHASH__', token) 
            if not match:
                fatal('Invalid identifier in RPN expression: ' + token)
            param = match.group(1)
            number = expandstring(token, params)
            stack.append(number)
        elif token == '+':
            if len(stack) < 2:
                fatal('Stack underflow for + operator in RPN ' + rpn)
            b = float(stack.pop())
            a = float(stack.pop())
            stack.append(str(a + b))
        elif token == '-':
            if len(stack) < 2:
                fatal('Stack underflow for - operator in RPN ' + rpn)
            b = float(stack.pop())
            a = float(stack.pop())
            stack.append(str(a - b))
        elif token == '*':
            if len(stack) < 2:
                fatal('Stack underflow for * operator in RPN ' + rpn)
            b = float(stack.pop())
            a = float(stack.pop())
            stack.append(str(a * b))
        elif token == '/':
            if len(stack) < 2:
                fatal('Stack underflow for / operator in RPN ' + rpn)
            b = float(stack.pop())
            a = float(stack.pop())
            stack.append(str(a / b))
    if len(stack) > 1:
        fatal('Extra items on stack after evaluation of RPN ' + rpn)
    if kind == 'Int':
        result = str(int(float(stack.pop())))
    elif kind == 'Float':
        result = str(float(stack.pop()))
    elif kind == 'String':
        result = str(stack.pop())
    verbose(level, 'Evaluated ' + rpn + ' as ' + result)
    return result

def evalparam(param, kind, level, params):
    if kind == 'Param':
        verbose(level, '**************** Param')
        return expandstring(param, params)
    else:
        return evalrpn(param, kind, level, params)

def evalcondition(type, elem, params):
    valid = elem.get('Valid')
    check = elem.get('Check')
    notempty = elem.get('NotEmpty')
    match = elem.get('Match')
    different = elem.get('Different')
    if ((valid or notempty) and (check or match or different)) or (match and different):
        fatal('Invalid combination of attributes for Condition element')
    if valid != None:
        value = params.get(valid)
        return value != None and value != '0' and value != 'False' and value != 'FALSE' and value != ''
    elif notempty != None:
        value = params.get(notempty)
        return value != None and value != ''
    else:
        value = expandparamname(params.get(check), params)
        if match != None:
            return value == match
        elif different != None:
            return value != different
        else:
            return value != None

def evalexpr(elem, level, params):
    verbose(level, 'Evaluating expression:')
    if args.verbose:
        writeelement(elem)
    verbose(level, 'With params: ' + str(params))
    if len(list(elem)) == 0:
        return elem.text
    elif len(list(elem)) == 1:
        op = list(elem)[0]
        if op.tag == 'And':
            if len(list(op)) != 2:
                fatal('Operator element "And" should have two child elements')
            a = expandparamname(evalexpr(list(op)[0], params), params)
            b = expandparamname(evalexpr(list(op)[1], params), params)
            if a == 'True' and b == 'True':
                return 'True'
            else:
                return 'False'
        elif op.tag == 'Or':
            if len(list(op)) != 2:
                fatal('Operator element "Or" should have two child elements')
            a = expandparamname(evalexpr(list(op)[0], params), params)
            b = expandparamname(evalexpr(list(op)[1], params), params)
            if a == 'True' or b == 'True':
                return 'True'
            else:
                return 'False'
        elif op.tag == 'Not':
            if len(list(op)) != 1:
                fatal('Operator element "Not" should have only one child element')
            a = expandparamname(evalexpr(list(op)[0], params), params)
            if a != 'True':
                return 'True'
            else:
                return 'False'
        elif op.tag == 'Greater':
            if len(list(op)) != 2:
                fatal('Operator element "Greater" should have two child elements')
            a = expandparamname(evalexpr(list(op)[0], params), params)
            b = expandparamname(evalexpr(list(op)[1], params), params)
            if int(a) > int(b):
                return 'True'
            else:
                return 'False'
        elif op.tag == 'Lower':
            if len(list(op)) != 2:
                fatal('Operator element "Lower" should have two child elements')
            a = expandparamname(evalexpr(list(op)[0], params), params)
            b = expandparamname(evalexpr(list(op)[1], params), params)
            if int(a) < int(b):
                return 'True'
            else:
                return 'False'
        elif op.tag == 'GreaterOrEqual':
            if len(list(op)) != 2:
                fatal('Operator element "GreaterOrEqual" should have two child elements')
            a = expandparamname(evalexpr(list(op)[0], params), params)
            b = expandparamname(evalexpr(list(op)[1], params), params)
            if int(a) >= int(b):
                return 'True'
            else:
                return 'False'
        elif op.tag == 'LowerOrEqual':
            if len(list(op)) != 2:
                fatal('Operator element "LowerOrEqual" should have two child elements')
            a = expandparamname(evalexpr(list(op)[0], params), params)
            b = expandparamname(evalexpr(list(op)[1], params), params)
            if int(a) <= int(b):
                return 'True'
            else:
                return 'False'
        elif op.tag == 'Equal':
            if len(list(op)) != 2:
                fatal('Operator element "LowerOrEqual" should have two child elements')
            a = expandparamname(evalexpr(list(op)[0], params), params)
            b = expandparamname(evalexpr(list(op)[1], params), params)
            if int(a) == int(b):
                return 'True'
            else:
                return 'False'
        elif op.tag == 'StringEqual':
            if len(list(op)) != 2:
                fatal('Operator element "LowerOrEqual" should have two child elements')
            a = expandparamname(evalexpr(list(op)[0], params), params)
            b = expandparamname(evalexpr(list(op)[1], params), params)
            if a == b:
                return 'True'
            else:
                return 'False'
        elif op.tag == 'Arg':
            if evalcondition('Arg', op, params):
                return 'True'
            else:
                return 'False'
        else:
            fatal('Unknown operator element "' + op.tag+ '"')

def expandcondition(siblings, ix, level, params):
    elem = siblings[ix]
    verbose(level, 'Expanding "Condition" element ' + elemtostring(elem))
    trues = elem.findall('True')
    falses = elem.findall('False')
    if len(trues) > 1 or len(falses) > 1:
        fatal('"Condition" element has too many True or False children')
    if len(elem.attrib.keys()) == 0:
        if len(list(elem)) == 0:
            fatal('Invalid "Condition" element with no attributes no children')
        elif len(list(elem)) == 1:
            fatal('Invalid "Condition" element with no attributes and just one child')
        test = list(elem)[0]
        if test.tag != 'Test':
            fatal('Invalid "Condition" element with no attributes but without a Test element as first child')
        success = evalexpr(test, params)
    else:
        success = evalcondition('Condition', siblings[ix], params)
    verbose(level, '  Condition evaluates as ' + str(success))
    siblings.pop(ix)
    if success:
        if len(trues) == 1:
            for i in list(trues[0]):
                verbose(level, '  Inserting subelement of "True" child: ' + elemtostring(i))
                siblings.insert(ix, i)
                ix += 1
        else:
            for i in list(elem):
                verbose(level, '  Inserting child: ' + elemtostring(i))
                siblings.insert(ix, i)
                ix += 1
    else:
        if len(falses) == 1:
            for i in list(falses[0]):
                verbose(level, '  Inserting subelement of "False" child: ' + elemtostring(i))
                siblings.insert(ix, i)
                ix += 1

def expandswitch(siblings, ix, level, params):
    elem = siblings[ix]
    cases = elem.findall('Case')
    defaults = elem.findall('Default')
    if len(defaults) > 1:
        fatal('"Switch" element has more than one "Default" child')
    if len(cases) == 0 and len(defaults) == 0:
        fatal('"Switch" element has neither "Case" or "Default" children')    
    if args.verbose:
        if len(defaults) == 0:
            numdefaults = 'no "Default" children'
        else:
            numdefaults = 'one "Default" child'
        verbose(level, 'Expanding "Switch" element with params ' + str(params))
        writeelement(elem)
    param = elem.get('Param')
    if param:
        param = expandparamname(param, params)
    expansion = None
    for case in cases:
        if param != None:
            if not case.get('Value'):
                fatal('"Switch" element has "Param" attribute but child "Case" element lacks "Value" attribute')
            if case.get('Valid') or case.get('Check') or case.get('NotEmpty') or case.get('Match') or case.get('Different'):
                fatal('"Switch" element has "Param" attribute but child "Case" element has more attributes than just "Value"')
            if param == expandparamname(case.get('Value')):
                expansion = list(case)
                break
    if expansion == None and len(defaults) == 1:
        expansion = list(defaults[0])
    siblings.pop(ix)
    for i in expansion:
        siblings.insert(ix, i)
        ix += 1

def expandusetemplate(siblings, ix, level, file, params):
    elem = siblings[ix]
    name = elem.attrib.get('Name')
    verbose(level, 'Expanding template "' + name + '" with ' + str(params))

    # Handle the arguments provided at the call site
    args = list(elem)
    argix = 0
    while argix < len(args):
        arg = args[argix]
        if arg.tag == 'Condition':
            expandcondition(args, argix, level, params)
        else:
            if arg.text != None:
                value = arg.text
            else:
                value = ''
            process = arg.get('Process')
            if process != None:
                value = evalparam(value, process, level, params)
            verbose(level, '  Argument ' + arg.tag + ': "' + value + '"')
            params[arg.tag] = value
        argix += 1

    template = templates.get(name)
    if not template:
        fatal(level, 'Calling undefined template "' + name + '"')
        
    defaults = template.find('DefaultTemplateParameters')
    if defaults:
        defaults = [ defaults ]
    if not defaults:
        defaults = template.findall("./Parameters[@Type='Default']")
    if defaults:
        for d in defaults:
            defs = list(d)
            defix = 0
            while defix < len(defs):
                p = defs[defix]
                if p.tag == 'Condition':
                  expandcondition(defs, defix, level, params)  
                else:
                    if not params.get(p.tag):
                        value = p.text
                        if value == None:
                            value = ''
                        process = p.get('Process')
                        if process != None:
                            value = evalparam(value, process, level, params)
                        verbose(level, '  Default parameter ' + p.tag + ': "' + value + '"')
                        params[p.tag] = value
                    else:
                        verbose(level, '  (Default parameter ' + p.tag + ' already provided in call stack)')
                    defix += 1

    overrides = template.find('OverrideTemplateParameters')
    if overrides:
        overrides = [ overrides ]
    if not overrides:
        overrides = template.findall("./Parameters[@Type='Override']")
    if overrides:
        for o in overrides:
            ovs = list(o)
            ovix = 0
            while ovix < len(ovs):
                p = ovs[ovix]
                if p.text != None:
                    value = p.text
                else:
                    value = None
                process = p.get('Process')
                if process != None:
                    value = evalparam(value, process, level, params)
                overridden = False
                if params.get(p.tag):
                    overridden = True
                    if value == None:
                        verbose(level, '  Parameter ' + p.tag + ' removed')
                    else:
                        verbose(level, '  Parameter ' + p.tag + ' overridden as: "' + value + '"')
                params[p.tag] = value
                if not overridden:
                    verbose(level, '  Parameter ' + p.tag + ': "' + value + '"')
                ovix += 1

    verbose(level, '  Popping element at ' + str(ix) + ': ' + elemtostring(siblings[ix]))
    siblings.pop(ix)
    for c in list(template):
        c = shallowcopyelement(c)
        if c.tag == 'Parameters' or c.tag == 'DefaultTemplateParameters' or c.tag == 'EditableTemplateParameters' or c.tag == 'OverrideTemplateParameters':
            pass
        else:
            siblings.insert(ix, expand(c, level + 1, file, params))
            verbose(level, '  Inserted element at ' + str(ix) + ' from template expansion:' + elemtostring(siblings[ix]))
            ix += 1

def expand(elem, level, file, params):
    verbose(level, 'Expanding ' + elemtostring(elem))
    didany = True
    kids = list(elem)
    ix = 0
    filestack = [ file ]
    while ix < len(kids):
        # verbose(level, 'kids[' + str(ix) + '] is ' + elemtostring(kids[ix]))
        kid = kids[ix]
        if kid.tag == 'FILE':
            pass
        elif kid.tag == 'Include':
            filename = kid.attrib.get('ModelBehaviorFile')
            if filename:
                filename = filename.replace('\\', '/')

                fullname = includedir + '/' + filename

            else:
                filename = kid.attrib.get('RelativeFile')
                if filename:
                    filename = filename.replace('\\', '/')

                    fullname = os.path.dirname(filestack[-1]) + '/' + filename
                else:
                    fatal('"Include" element without "ModelBehaviorFile" or "RelativeFile" attribute');

                kids.pop(ix)

                if included.get(fullname):
                    pass
                else:
                    includedtree = parse(fullname)
                    filestack.push(fullname)
                    kids.insert(ix, ET.Element('FILE', { "Path": filestack[-1] }))
                    ix += 1

                    for i in includedtree:
                        kids.insert(ix, i)
                        ix += 1
                    filestack.pop()

                    kids.insert(ix, ET.Element('FILE', { "Path": filestack[-1] }))
                    ix += 1
            included[fullname] = True
        elif kid.tag == 'Template' or kid.tag == 'InputEvent':
            name = kid.attrib.get('Name')
            if not name:
                fatal('No Name attribute in "Template" or "InputEvent" element')
            if templates.get(name):
                fatal('Multiply defined template "' + name + '"')
            verbose(level, 'Defined template "' + name + '" as ' + elemtostring(kid))
            templates[name] = kid
            kids.pop(ix)
        elif kid.tag == 'Condition':
            expandcondition(kids, ix, level, params)
        elif kid.tag == 'Switch':
            expandswitch(kids, ix, level, params)
        elif kid.tag == 'UseTemplate':
            name = kid.attrib.get('Name')
            if not name:
                fatal('No Name attribute in UseTemplate element')
            name = expandstring(name, params)
            expandusetemplate(kids, ix, level + 1, filestack[-1], params.copy())
        else:
            expand(kid, level, filestack[-1], params.copy())
            ix += 1
    # Now drop all original children of elem and insert the expanded children instead
    removechildren(elem)
    for kid in kids:
        elem.append(kid)

    return elem
        
def remove(elem, tag):
    for i in list(elem):
        if i.tag == tag:
            elem.remove(i)
        else:
            remove(i, tag)

# Load the input file
tree = parse(args.input)

# Do the actual work, 
expand(tree, 0, args.input, { })

# And now we can drop the Template elements and their children
remove(tree, 'Template')

ET.ElementTree(tree).write(sys.stdout, encoding='Unicode')

