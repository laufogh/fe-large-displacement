from fldlib import ale


class Node(object):
    def __init__(self, coordinates):
        self.coordinates = coordinates


class Element(object):
    def __init__(self, label, coordinates):
        self.label = label
        self._nodes = [Node(coordinates)]

    def getNodes(self):
        return self._nodes


class ElementArray(list):
    def __getitem__(self, item):
        result = list.__getitem__(self, item)
        return ElementArray(result) if isinstance(item, slice) else result

    def __add__(self, other):
        return ElementArray(list(self) + list(other))


class Instance(object):
    def __init__(self, elements):
        self.elements = ElementArray(elements)


class ElementSet(object):
    def __init__(self, elements):
        self.elements = elements


class Assembly(object):
    def __init__(self):
        self.sets = {}

    def Set(self, name, elements):
        self.sets[name] = ElementSet(elements)
        return self.sets[name]


def test_cylindrical_sets_separate_plug_and_skirt_annulus():
    instance = Instance([
        Element(1, (0.10, 0.10, -0.1)),
        Element(2, (0.45, 0.00, -0.1)),
        Element(3, (0.75, 0.00, -0.1)),
        Element(4, (0.90, 0.00, -0.1)),
        Element(5, (1.20, 0.00, -0.1)),
    ])
    assembly = Assembly()

    ale.cylindrical_element_set(
        assembly, instance, 'Plug', 0.0, 0.5, -0.2, 0.0)
    ale.cylindrical_element_set(
        assembly, instance, 'Tip', 0.7, 1.0, -0.2, 0.0)

    plug = set(el.label for el in assembly.sets['Plug'].elements)
    tip = set(el.label for el in assembly.sets['Tip'].elements)
    assert plug == {1, 2}
    assert tip == {3, 4}
    assert not plug.intersection(tip)


def test_cylindrical_set_rejects_invalid_radial_range():
    try:
        ale.cylindrical_element_set(
            Assembly(), Instance([]), 'bad', 1.0, 1.0, -1.0, 0.0)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid radial range was accepted')
