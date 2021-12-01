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

if os.path.dirname(args.input) == '':
    args.input = './' + args.input

NUMBER = r'-?\d+(?:\.\d+)?'
IDENTIFIER = r'[_A-Za-z][_A-Za-z0-9]*'

templates = { }
inputevents = { }

included = { }

def verbose(indent, string):
    if args.verbose:
        s = ''
        for i in range(indent):
            s += '    '
        print(s + string, file=sys.stderr)

def fatal(string):
    print('\n' + string, file=sys.stderr)
    exit(1)

def filemarker(path):
    if path == None:
        result = ET.Element('EOF')
    else:
        result = ET.Element('FILE', { 'Path': path })
    result.tail = '\n'
    return result

def cleanpathname(path):
    # Use forward slashes so that this script can be run also on Unix for convenience
    result = path.replace('\\', '/')
    result = result.replace('//', '/')
    return result

def treetostring(depth, compress, elem):
    result = '<' + elem.tag;
    for i in elem.keys():
        result += ' ' + i + '="' + elem.get(i) + '"'
    if elem.text == None and len(list(elem)) == 0:
        result += '/>'
        return result
    result += '>'
    if elem.text != None:
        if compress:
            result += re.sub(r'\s+', ' ', elem.text)
        else:
            result += elem.text
    if depth == 0 and len(list(elem)) > 0:
        result += '...'
    else:
        for i in list(elem):
            result += treetostring(depth - 1, compress, i)
            lasttail = list(elem)[-1].tail
            if compress:
                result += re.sub(r'\s+', ' ', lasttail)
            else:
                result += lasttail
    result += '</' + elem.tag + '>'
    return result

def elemtostring(elem):
    return treetostring(0, True, elem)

def parse(filename):
    with open(filename, 'r') as f:
        data = f.read()
        data = re.sub('#(' + IDENTIFIER + ')#', r'__HASH__\1__HSAH__', data)
        # The RPN in some files uses & and > as such. Try to fix those,
        data = re.sub(' > if{', ' &gt; if{', data)
        data = re.sub(' & ', ' &amp; ', data)
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

def deepcopytree(root):
    root = shallowcopyelement(root)
    kids = list(root)
    removechildren(root)
    for kid in list(kids):
        root.append(deepcopytree(kid))
    return root

def expandparamname(name, params):
    value = params.get(name)
    if value != None:
        return value
    return None

def expandstring(string, params):
    if string == None:
        return None
    if string.find('__HASH__') == -1:
        return string
    for key, value in params.items():
        string = re.sub('__HASH__' + key + '__HSAH__', value, string)
    # Remove unexpanded leftover parameter referenced
    string = re.sub('__HASH__' + IDENTIFIER + '__HSAH__', '', string)
    return string

def evalrpn(rpn, kind, indent, params):
    verbose(indent, 'Evaluating ' + kind + ' RPN: "' + rpn + '"')
    tokens = re.findall(NUMBER + '|' + IDENTIFIER + '|' + r'-?\d+(?:\.\d+)?|[_A-Za-z][_A-Za-z0-9]+|\+|-|\*|/|\s+|.', rpn)
    stack = []
    for token in tokens:
        if re.fullmatch(r'\s+', token):
            # Whitespace
            pass
        elif re.fullmatch(NUMBER, token):
            stack.append(float(token))
        elif re.fullmatch(IDENTIFIER, token):
            match = re.fullmatch('__HASH__(' + IDENTIFIER + ')__HSAH__', token) 
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
        else:
            # Unrecognized token, let's assume it is a run-time expression
            return rpn
    if len(stack) > 1:
        fatal('Extra items on stack after evaluation of RPN ' + rpn)
    if kind == 'Int':
        result = str(int(float(stack.pop())))
    elif kind == 'Float':
        result = str(float(stack.pop()))
    elif kind == 'String':
        result = str(stack.pop())
    verbose(indent, 'Evaluated "' + rpn + '" as "' + result + '"')
    return result

def evalparam(param, kind, indent, params):
    if kind == 'Param':
        name = expandstring(param, params)
        value = params.get(name)
        if value == None:
            value = ''
        return value
    else:
        return evalrpn(param, kind, indent, params)

def evalcondition(type, elem, params):
    valid = elem.get('Valid')
    check = elem.get('Check')
    notempty = elem.get('NotEmpty')
    match = elem.get('Match')
    different = elem.get('Different')
    if ((valid or notempty) and (check or match or different)) or (match and different):
        fatal('Invalid combination of attributes for ' + type + ' element')
    if valid != None:
        value = params.get(valid)
        if value != None and value != '0' and value != 'False' and value != 'FALSE' and value != '':
            return 'True'
        else:
            return 'False'
    elif notempty != None:
        value = params.get(notempty)
        if value != None and value != '':
            return 'True'
        else:
            return 'False'
    else:
        value = expandparamname(check, params)
        if match != None:
            if value == match:
                return 'True'
            else:
                return 'False'
        elif different != None:
            if value != different:
                return 'True'
            else:
                return 'False'
        else:
            if value != None:
                return 'True'
            else:
                return 'False'

def evalexpr(elem, indent, params):
    verbose(indent, 'Evaluating expression: ' + treetostring(1, True, elem))
    if len(list(elem)) == 0:
        if elem.tag == 'Arg':
            return evalcondition('Arg', elem, params)
        elif elem.tag == 'Value':
            result = expandparamname(elem.text, params)
            # Sigh, it is OK to use Value for a nonexistent parameter,
            # and that apparently means zero.
            if result == None:
                return '0'
            else:
                return result
        elif elem.tag == 'Number':
            return elem.text
        else:
            fatal('Unknown terminal expression element "' + elem.tag + '"')
    elif len(list(elem)) == 1:
        if elem.tag == 'Not':
            a = expandparamname(evalexpr(list(elem)[0], indent + 1, params), params)
            if a != 'True':
                return 'True'
            else:
                return 'False'
        else:
            fatal('Unknown unary operator "' + elem.tag + '"')
    elif elem.tag == 'And':
        if len(elem) == 0:
            fatal('No children for And operator')
        kidix = 0
        while kidix < len(list(elem)):
            a = expandparamname(evalexpr(list(elem)[kidix], indent + 1, params), params)
            if a != 'True':
                return 'False'
            kidix += 1
        return 'True'
    elif elem.tag == 'Or':
        if len(elem) == 0:
            fatal('No children for Or operator')
        kidix = 0
        while kidix < len(list(elem)):
            a = expandparamname(evalexpr(list(elem)[0], indent + 1, params), params)
            if a == 'True':
                return 'True'
            kidix += 1
        return 'False'
    elif len(list(elem)) == 2:
        if elem.tag == 'Greater':
            a = evalexpr(list(elem)[0], indent + 1, params)
            b = evalexpr(list(elem)[1], indent + 1, params)
            if float(a) > float(b):
                return 'True'
            else:
                return 'False'
        elif elem.tag == 'Lower':
            a = evalexpr(list(elem)[0], indent + 1, params)
            b = evalexpr(list(elem)[1], indent + 1, params)
            if float(a) < float(b):
                return 'True'
            else:
                return 'False'
        elif elem.tag == 'GreaterOrEqual':
            a = evalexpr(list(elem)[0], indent + 1, params)
            b = evalexpr(list(elem)[1], indent + 1, params)
            if float(a) >= float(b):
                return 'True'
            else:
                return 'False'
        elif elem.tag == 'LowerOrEqual':
            a = evalexpr(list(elem)[0], indent + 1, params)
            b = evalexpr(list(elem)[1], indent + 1, params)
            if float(a) <= float(b):
                return 'True'
            else:
                return 'False'
        elif elem.tag == 'Equal':
            a = evalexpr(list(elem)[0], indent + 1, params)
            b = evalexpr(list(elem)[1], indent + 1, params)
            if float(a) == float(b):
                return 'True'
            else:
                return 'False'
        elif elem.tag == 'StringEqual':
            a = evalexpr(list(elem)[0], indent + 1, params)
            b = evalexpr(list(elem)[1], indent + 1, params)
            if a == b:
                return 'True'
            else:
                return 'False'
        else:
            fatal('Unknown binary operator "' + op.tag+ '"')
    else:
        fatal('Weird expression ' + treetostring(1, True, elem))

def expandcondition(siblings, ix, indent, params):
    elem = siblings[ix]
    trues = elem.findall('True')
    falses = elem.findall('False')
    if len(trues) > 1 or len(falses) > 1:
        fatal('"Condition" element has too many True or False children')
    verbose(indent, 'Expanding ' + elemtostring(elem) + ' with ' + str(params))
    if len(elem.keys()) == 0:
        if len(list(elem)) == 0:
            fatal('Invalid "Condition" element with no attributes no children')
        elif len(list(elem)) == 1:
            fatal('Invalid "Condition" element with no attributes and just one child')
        test = list(elem)[0]
        if test.tag != 'Test':
            fatal('Invalid "Condition" element with no attributes but without a Test element as first child')
        # The Test element apparently can have multiple children. In
        # that case an And operator is implied, it seems.
        success = True
        for i in list(test):
            if success:
                success = success and evalexpr(i, indent, params)
    else:
        success = evalcondition('Condition', siblings[ix], params)
    verbose(indent, ' Condition evaluates as ' + str(success))
    siblings.pop(ix)
    if success == 'True':
        if len(trues) == 1:
            for i in list(trues[0]):
                verbose(indent, ' Inserting subelement of "True" child: ' + elemtostring(i))
                siblings.insert(ix, i)
                ix += 1
        else:
            for i in list(elem):
                if i.tag == 'Test':
                    continue
                verbose(indent, ' Inserting child: ' + elemtostring(i))
                siblings.insert(ix, i)
                ix += 1
    else:
        if len(falses) == 1:
            for i in list(falses[0]):
                verbose(indent, ' Inserting subelement of "False" child: ' + elemtostring(i))
                siblings.insert(ix, i)
                ix += 1

def expandswitch(siblings, ix, indent, params):
    elem = siblings[ix]
    cases = elem.findall('Case')
    defaults = elem.findall('Default')
    if len(defaults) > 1:
        fatal('"Switch" element has more than one "Default" child')
    if len(cases) == 0 and len(defaults) == 0:
        fatal('"Switch" element has neither "Case" or "Default" children')    
    verbose(indent, 'Expanding ' + elemtostring(elem) + ' with ' + str(params))
    param = elem.get('Param')
    if param:
        param = expandparamname(param, params)
    expansion = None
    for case in cases:
        # Despite what the SDK docs say, even if the Switch element
        # has a Param attribute, not all Case elements need to have a
        # Value attribute. A Case element might also just have a
        # Valid, Check, or Notempty attribute.

        # Apparently parameter expansion #PARAMNAME# is not done on
        # Value attributes.
        value = case.get('Value')
        if value != None and param != None:
            if param == value:
                expansion = list(case)
                break
        valid = case.get('Valid')
        if valid != None:
            valid = expandparamname(valid, params)
            if valid != None and valid != '' and valid != '0' and valid != 'False':
                expansion = list(case)
                break
        check = case.get('Check')
        if check != None:
            # The Check attribute contains a parameter name
            check = expandparamname(check, params)
            # The Match and Different attributes are always just string literals
            match = case.get('Match')
            different = case.get('Different')
            if match != None:
                if check == match:
                    expansion = list(case)
                    break
            elif different != None:
                if check != different:
                    expansion = list(case)
                    break
            elif check != None:
                expansion = list(case)
                break
        notempty = case.get('NotEmpty')
        if notempty != None:
            notempty = expandparamname(notempty, params)
            if notempty != None and notempty != '':
                expansion = list(case)
                break
    if expansion == None and len(defaults) == 1:
        expansion = list(defaults[0])
    siblings.pop(ix)
    if expansion != None:
        for i in expansion:
            siblings.insert(ix, i)
            ix += 1

def expandloop(siblings, ix, indent, params):
    elem = siblings[ix]
    params = params.copy()
    verbose(indent, 'Expanding ' + treetostring(2, True, elem) + ' with ' + str(params))
    l = elem.findall('Setup')
    if len(l) == 0:
        fatal('"Loop" element with no "Setup" child')
    if len(l) > 1:
        fatal('"Loop" element with more than one "Setup" child')
    setup = l[0]
    l = elem.findall('Do')
    if len(l) == 0:
        fatal('"Loop" element with no "Do" child')
    if len(l) > 1:
        fatal('"Loop" element with more than one "Do" child')
    do = l[0]
    l = elem.findall('Then')
    if len(l) > 1:
        fatal('"Loop" element with more than one "Then" child')
    then = None
    if len(l) == 1:
        then = l[0]
    if len(setup.findall('Param')) != 1 or len(setup.findall('From')) != 1 or len(setup.findall('Inc')) > 1 \
       or len(setup.findall('To')) > 1 or len(setup.findall('While')) > 1 \
       or (len(setup.findall('To')) == 1 and len(setup.findall('While')) == 1):
        fatal('"Loop" element syntax error')

    var = setup.find('Param').text
    loopvar = float(expandstring(setup.find('From').text, params))
    inc = setup.find('Inc')
    if inc != None:
        inc = float(expandstring(inc.text, params))
    else:
        inc = 1
    to = setup.find('To')
    if to != None:
        to = float(expandstring(to.text, params))
    hwile = setup.find('While')
    if hwile != None and len(hwile) != 1:
        fatal('Invalid While tree ' + treetostring(1, True, hwile))

    params[var] = str(loopvar)
    numiters = 0

    siblings.pop(ix)
    while True:
        for i in list(do):
            i = shallowcopyelement(i)
            i.text = expandstring(i.text, params)
            i.tail = expandstring(i.tail, params)
            siblings.insert(ix, i)
            ix += 1
        numiters += 1
        if to == None and hwile == None and numiters == 64:
            break
        loopvar += inc
        params[var] = str(loopvar)
        if to != None and ((inc > 0 and loopvar >= to) or (inc < 0 and loopvar <= to)):
            break
        if hwile != None:
            if evalexpr(list(hwile)[0], indent, params) == 'False':
                break
    # Set the tail of the original Loop element to the last of the inserted elements
    siblings[ix-1].tail = elem.tail

def expandusetemplate(siblings, ix, indent, file, params):
    elem = siblings[ix]
    params = params.copy()

    name = elem.get('Name')
    if not name:
        fatal('No Name attribute in UseTemplate element')
    name = expandstring(name, params)

    verbose(indent, 'Expanding ' + elemtostring(elem) + ' with ' + str(params))
    template = templates.get(name)
    if not template:
        verbose(indent, 'Undefined template "' + name + '"')
        siblings.pop(ix)
        return
        
    # Handle the arguments provided at the call site
    expand(elem, indent, file, params)

    for arg in list(elem):
        if arg.text != None:
            value = arg.text
        else:
            value = ''
        process = arg.get('Process')
        if process != None:
            value = evalparam(value, process, indent, params)
        verbose(indent, ' Call parameter ' + arg.tag + ': "' + value + '"')
        params[arg.tag] = value

    template = deepcopytree(template)
    template = expandintemplate(template, indent, file, params)

    verbose(indent, ' Popping element at ' + str(ix) + ': ' + elemtostring(siblings[ix]))
    siblings.pop(ix)
    for c in list(template):
        c = shallowcopyelement(c)
        verbose(indent, ' Inserting element at ' + str(ix) + ' from template expansion:' + elemtostring(c))
        siblings.insert(ix, expand(c, indent + 1, file, params))
        ix += 1

def expandparameters(siblings, ix, indent, file, params):
    elem = siblings[ix]
    verbose(indent, 'Expanding ' + elemtostring(elem) + ' with ' + str(params))
    type = elem.get('Type')
    if elem.tag == 'DefaultTemplateParameters' \
       or (elem.tag == 'Parameters' and type == 'Default'):
        kind = 'Default'
    elif elem.tag == 'OverrideTemplateParameters' \
         or (elem.tag == 'Parameters' and type == 'Override'):
        kind = 'Override'
    elif elem.tag == 'EditableTemplateParameters':
        kind = 'Editable'
    else:
        fatal('Unrecognized parameter list type ' + elemtostring(elem))

    # No idea what EditableTemplateParameters mean, just skip it
    if kind == 'Editable':
        siblings.pop(ix)
        return

    kids = list(elem)
    kidix = 0
    while kidix < len(kids):
        dummy = expandtomany(kids[kidix], indent, file, params)
        kids.pop(kidix)
        newkidix = kidix
        l = list(dummy)
        for i in list(dummy):
            kids.insert(newkidix, i)
            newkidix += 1
        if kidix == len(kids):
            break
        p = kids[kidix]
        value = p.text
        if value == None:
            value = ''
        verbose(indent, kind + ' parameter ' + p.tag + ': "' + value + '"')
        if kind == 'Override' or params.get(p.tag) == None:
            process = p.get('Process')
            if process != None:
                value = evalparam(value, process, indent, params)
            params[p.tag] = value
        else:
            verbose(indent, ' (Default parameter ' + p.tag + ' already provided in call stack)')
        kidix += 1
    verbose(indent, 'Popping element at ' + str(ix) + ': ' + elemtostring(elem))
    siblings.pop(ix)

def expand2(intemplate, elem, indent, file, params):
    didany = True
    kids = list(elem)
    verbose(indent, 'Expanding ' + elemtostring(elem) + ' with ' + str(len(kids)) + ' children')
    ix = 0
    filestack = [ file ]

    while ix < len(kids):
        verbose(indent, ' kids[' + str(ix) + '] is ' + elemtostring(kids[ix]))
        kid = shallowcopyelement(kids[ix])
        for i in kid.keys():
            kid.set(i, expandstring(kid.get(i), params))

        if kid.tag == 'FILE':
            filestack.append(kid.get('Path'))
            kids.pop(ix)
        elif kid.tag == 'EOF':
            filestack.pop()
            kids.pop(ix)
        elif kid.tag == 'Include':
            filename = kid.get('ModelBehaviorFile')
            if filename == None:
                filename = kid.get('Path')
            if filename:
                filename = cleanpathname(filename)
                fullname = includedir + '/' + filename
            else:
                filename = kid.get('RelativeFile')
                if filename:
                    filename = cleanpathname(filename)
                    fullname = os.path.dirname(filestack[-1]) + '/' + filename
                else:
                    fatal('"Include" element without "ModelBehaviorFile", "Path", or "RelativeFile" attribute');

            kids.pop(ix)

            if included.get(fullname.lower()):
                ix -= 1
            else:
                addix = ix
                includedtree = parse(fullname)
                kids.insert(addix, filemarker(fullname))
                addix += 1

                for i in includedtree:
                    kids.insert(addix, i)
                    addix += 1

                kids.insert(addix, filemarker(None))
                addix += 1
                kids.insert(addix, filemarker(filestack[-1]))
                addix += 1
                included[fullname.lower()] = True
                verbose(indent, 'Included file "' + fullname + '"')
        elif kid.tag == 'Template':
            name = kid.get('Name')
            if not name:
                fatal('No Name attribute in "Template" element')
            if templates.get(name):
                fatal('Multiply defined template "' + name + '"')
            verbose(indent, 'Defined template "' + name + '"')
            templates[name] = kid
            kids.pop(ix)
        elif kid.tag == 'InputEvent':
            id = kid.get('ID')
            if not id:
                fatal('No ID attribute in "InputEvent" element')
            if inputevents.get(id):
                fatal('Multiply defined input event "' + id + '"')
            verbose(indent, 'Defined input event "' + id + '"')
            inputevents[id] = kid
            kids.pop(ix)
        elif kid.tag == 'Condition':
            expandcondition(kids, ix, indent, params)
        elif kid.tag == 'Switch':
            expandswitch(kids, ix, indent, params)
        elif kid.tag == 'Loop':
            expandloop(kids, ix, indent, params)
        elif kid.tag == 'UseTemplate':
            expandusetemplate(kids, ix, indent + 1, filestack[-1], params)
        elif intemplate \
             and (kid.tag == 'Parameters' \
                  or kid.tag == 'DefaultTemplateParameters' \
                  or kid.tag == 'EditableTemplateParameters' \
                  or kid.tag == 'OverrideTemplateParameters'):
            expandparameters(kids, ix, indent + 1, file, params)
        else:
            kids[ix] = expand(kid, indent + 1, filestack[-1], params.copy())
            kids[ix].text = expandstring(kid.text, params)
            kids[ix].tail = expandstring(kid.tail, params)
            ix += 1

    # Now drop all original children of elem and insert the expanded children instead
    removechildren(elem)
    for kid in kids:
        elem.append(kid)
    return elem
        
def expand(elem, indent, file, params):
    return expand2(False, elem, indent, file, params)

def expandtomany(elem, indent, file, params):
    dummy = ET.Element('DUMMY')
    dummy.append(elem)
    return expand2(False, dummy, indent, file, params)

def expandintemplate(elem, indent, file, params):
    return expand2(True, elem, indent, file, params)


# Load the input file
tree = parse(args.input)

# Do the actual work, 
expand(tree, 0, args.input, { })

ET.ElementTree(tree).write(sys.stdout, encoding='Unicode')
sys.stdout.write('\n')
