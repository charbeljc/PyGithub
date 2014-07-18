# -*- coding: utf-8 -*-

# Copyright 2013-2014 Vincent Jacques <vincent@vincent-jacques.net>

import collections
import itertools
import re

import CodeGeneration.ApiDefinition.Structured as Structured
import CodeGeneration.ApiDefinition.Typing as Typing


# @todoAlpha Detect classes/structures with the same attributes (GitCommit.Author and GitTag.Tagger)

class EndPoint(object):
    def __init__(self, verb, url, parameters, doc):
        self.__verb = verb
        self.__url = url
        self.__urlTemplate = re.sub(":([a-z]+)", "{\\1}", url)
        self.__parameters = parameters
        self.__doc = doc

        self.__methods = []

    def _reference(self, typesRepo, endPointsRepo):
        pass

    def _propagate(self):
        pass

    def _finalize(self):
        self.__methods = sorted(self.__methods, key=lambda m: (m.containerClass.name, m.name))

    def _addMethod(self, method):
        self.__methods.append(method)

    @property
    def verb(self):
        return self.__verb

    @property
    def url(self):
        return self.__url

    @property
    def parameters(self):
        return self.__parameters

    @property
    def doc(self):
        return self.__doc

    @property
    def methods(self):
        return self.__methods

    @property
    def urlTemplate(self):
        return self.__urlTemplate


class AttributedType(Typing.SimpleType):
    def __init__(self, name, category, updatable, attributes, deprecatedAttributes):
        Typing.Type.__init__(self, name, category)
        self.__updatable = updatable
        self.__attributes = sorted((Attribute(self, *a) for a in attributes), key=lambda a: a.name)
        self.__deprecatedAttributes = sorted(deprecatedAttributes)
        self.__factories = []

    def _reference(self, typesRepo, endPointsRepo):
        for a in self.__attributes:
            a._reference(typesRepo, endPointsRepo)

    def _propagate(self):
        for a in self.__attributes:
            a._propagate()

    def _finalize(self):
        self.__factories = sorted(self.__factories, key=lambda f: (f.object.containerClass.name, f.object.name))

        for a in self.__attributes:
            a._finalize()

    def _addFactory(self, f):
        self.__factories.append(f)

    @property
    def factories(self):
        return self.__factories

    @property
    def deprecatedAttributes(self):
        return self.__deprecatedAttributes

    @property
    def attributes(self):
        return self.__attributes

    @property
    def isUpdatable(self):
        return self.__updatable


class Member(object):
    def __init__(self, containerClass):
        self.__containerClass = containerClass

    @property
    def containerClass(self):
        return self.__containerClass


class Attribute(Member):
    def __init__(self, containerClass, name, type):
        Member.__init__(self, containerClass)
        self.__name = name

        self.__tmp_typeDescription = type

    def _reference(self, typesRepo, endPointsRepo):
        self.__type = typesRepo.get(self.__tmp_typeDescription)
        del self.__tmp_typeDescription

    def _propagate(self):
        for t in self.__type.underlyingTypes:
            if isinstance(t, AttributedType):
                t._addFactory(Factory("attribute", self))

    def _finalize(self):
        pass

    @property
    def name(self):
        return self.__name

    @property
    def type(self):
        return self.__type


class Argument(object):
    def __init__(self, name, value):
        self.__name = name
        self.__value = Value(value)

    @property
    def name(self):
        return self.__name

    @property
    def value(self):
        return self.__value


def Value(value):
    return globals()[value.__class__.__name__](*value)  # Why not...


AttributeValue = collections.namedtuple("AttributeValue", "attribute")
EndPointValue = collections.namedtuple("EndPointValue", "")
ParameterValue = collections.namedtuple("ParameterValue", "parameter")
RepositoryOwnerValue = collections.namedtuple("RepositoryOwnerValue", "repository")
RepositoryNameValue = collections.namedtuple("RepositoryNameValue", "repository")

Factory = collections.namedtuple("Factory", "category, object")


class Class(AttributedType):
    def __init__(self, module, name, updatable, base, structures, attributes, methods, deprecatedAttributes):
        AttributedType.__init__(self, name, "class", updatable, attributes, deprecatedAttributes)
        self.__module = module
        self.__structures = sorted((Structure(self, *s) for s in structures), key=lambda s: s.name)
        self.__methods = sorted((Method(self, *m) for m in methods), key=lambda m: m.name)
        self.__derived = []

        self.__tmp_baseTypeDescription = base

    def _reference(self, typesRepo, endPointsRepo):
        AttributedType._reference(self, typesRepo, endPointsRepo)

        for s in self.__structures:
            s._reference(typesRepo, endPointsRepo)

        for m in self.__methods:
            m._reference(typesRepo, endPointsRepo)

        if self.__tmp_baseTypeDescription is None:
            if self.isUpdatable:
                self.__tmp_baseTypeDescription = Structured.ScalarType("UpdatableGithubObject")
            else:
                self.__tmp_baseTypeDescription = Structured.ScalarType("SessionedGithubObject")
        self.__base = typesRepo.get(self.__tmp_baseTypeDescription)
        self.__base.__derived.append(self)
        del self.__tmp_baseTypeDescription

    def _propagate(self):
        AttributedType._propagate(self)

        for s in self.__structures:
            s._propagate()

        for m in self.__methods:
            m._propagate()

    def _finalize(self):
        AttributedType._finalize(self)

        for s in self.__structures:
            s._finalize()

        for m in self.__methods:
            m._finalize()

        self.__derived = sorted(self.__derived, key=lambda d: d.name)

    @property
    def module(self):
        return self.__module

    @property
    def base(self):
        return self.__base

    @property
    def derived(self):
        return self.__derived

    @property
    def structures(self):
        return self.__structures

    @property
    def methods(self):
        return self.__methods


class Structure(AttributedType, Member):
    def __init__(self, containerClass, name, updatable, attributes, deprecatedAttributes):
        AttributedType.__init__(self, name, "struct", updatable, attributes, deprecatedAttributes)
        Member.__init__(self, containerClass)


class Method(Member):
    def __init__(self, containerClass, name, endPoints, parameters, urlTemplate, urlTemplateArguments, urlArguments, postArguments, effects, returnFrom, returnType):
        Member.__init__(self, containerClass)
        self.__name = name
        self.__parameters = [Parameter(*p) for p in parameters]
        self.__urlTemplate = Value(urlTemplate)
        self.__urlTemplateArguments = [Argument(*a) for a in urlTemplateArguments]
        self.__urlArguments = [Argument(*a) for a in urlArguments]
        self.__postArguments = [Argument(*a) for a in postArguments]
        self.__effects = effects
        self.__returnFrom = returnFrom

        self.__tmp_endPointDescriptions = endPoints
        self.__tmp_returnTypeDescription = returnType

    def _reference(self, typesRepo, endPointsRepo):
        for p in self.__parameters:
            p._reference(typesRepo, endPointsRepo)

        self.__endPoints = sorted((endPointsRepo.get(ep) for ep in self.__tmp_endPointDescriptions), key=lambda ep: (ep.url, ep.verb))
        del self.__tmp_endPointDescriptions

        self.__returnType = typesRepo.get(self.__tmp_returnTypeDescription)
        del self.__tmp_returnTypeDescription

    def _propagate(self):
        for p in self.__parameters:
            p._propagate()

        for ep in self.__endPoints:
            ep._addMethod(self)

        for t in self.__returnType.underlyingTypes:
            if isinstance(t, AttributedType):
                t._addFactory(Factory("method", self))

    def _finalize(self):
        for p in self.__parameters:
            p._finalize()

        self.__displayWarnings()

    def __displayWarnings(self):  # pragma no cover
        for ep in self.__endPoints:
            unimplementedParameters = set(ep.parameters) - set(p.name for p in self.__parameters)
            # @todoGeni Put those special cases in .yml definition files
            if self.containerClass.name == "AuthenticatedUser" and self.__name == "create_repo":
                unimplementedParameters.remove("team_id")
            if self.containerClass.name in ["AuthenticatedUser", "User", "Organization"] and self.__name == "create_fork":
                unimplementedParameters.remove("organization")
            if self.containerClass.name == "AuthenticatedUser" and self.__name == "edit":
                unimplementedParameters.remove("bio")
            if self.containerClass.name == "Repository" and self.__name == "edit":
                unimplementedParameters.remove("has_downloads")
            if self.containerClass.name == "Repository" and self.__name == "create_git_commit":
                unimplementedParameters.remove("name")
                unimplementedParameters.remove("date")
                unimplementedParameters.remove("email")
            if self.containerClass.name == "Repository" and self.__name == "create_git_tag":
                unimplementedParameters.remove("name")
                unimplementedParameters.remove("date")
                unimplementedParameters.remove("email")
                unimplementedParameters.remove("type")
            if self.containerClass.name == "Repository" and self.__name == "create_file":
                unimplementedParameters.remove("sha")
                unimplementedParameters.remove("name")
                unimplementedParameters.remove("email")
            if self.containerClass.name == "File" and self.__name in ["edit", "delete"]:
                unimplementedParameters.remove("sha")
                unimplementedParameters.remove("name")
                unimplementedParameters.remove("email")
                unimplementedParameters.remove("path")
                unimplementedParameters.remove("branch")
            if self.containerClass.name == "Dir" and self.__name in ["get_contents"]:
                unimplementedParameters.remove("path")
                unimplementedParameters.remove("ref")
            if self.containerClass.name == "Gist" and self.__name in ["edit"]:
                unimplementedParameters.remove("filename")
                unimplementedParameters.remove("content")
            if self.containerClass.name == "Repository" and self.__name == "create_git_tree" or self.containerClass.name == "GitTree" and self.__name == "create_modified_copy":
                unimplementedParameters.remove("sha")
                unimplementedParameters.remove("mode")
                unimplementedParameters.remove("base_tree")
                unimplementedParameters.remove("path")
                unimplementedParameters.remove("type")
                unimplementedParameters.remove("content")
            if len(unimplementedParameters) > 0:
                print("WARNING:", self.containerClass.name + "." + self.__name, "does not implement following parameters:", ", ".join(unimplementedParameters))

        unusedParameters = (
            set(p.name for p in self.__parameters)
            - set(a.value.parameter for a in itertools.chain(self.__urlTemplateArguments, self.__urlArguments, self.__postArguments) if isinstance(a.value, ParameterValue))
            - set(a.value.repository for a in itertools.chain(self.__urlTemplateArguments, self.__urlArguments, self.__postArguments) if isinstance(a.value, (RepositoryNameValue, RepositoryOwnerValue)))
        )
        if len(unusedParameters) > 0:
            print("WARNING:", self.containerClass.name + "." + self.__name, "does not use following parameters:", ", ".join(unusedParameters))

    @property
    def name(self):
        return self.__name

    @property
    def endPoints(self):
        return self.__endPoints

    @property
    def parameters(self):
        return self.__parameters

    @property
    def urlTemplate(self):
        return self.__urlTemplate

    @property
    def urlTemplateArguments(self):
        return self.__urlTemplateArguments

    @property
    def postArguments(self):
        return self.__postArguments

    @property
    def urlArguments(self):
        return self.__urlArguments

    @property
    def returnFrom(self):
        return self.__returnFrom

    @property
    def returnType(self):
        return self.__returnType

    @property
    def effects(self):
        return self.__effects


class Parameter(object):
    def __init__(self, name, type, orig, optional):
        self.__name = name
        self.__optional = optional
        # @todoGeni Couldn't we do something to factorize all this "descrition -> type" logic? Maybe with a metaclass?
        self.__tmp_originDescription = orig
        self.__tmp_typeDescription = type

    def _reference(self, typesRepo, endPointsRepo):
        if self.__tmp_typeDescription is None:
            types = [
                typesRepo.get(self.__tmp_originDescription.type),
                Typing.BuiltinType("int") if self.__tmp_originDescription.attribute == "id" else Typing.BuiltinType("string")  # @todoGeni Get the type of the attribute self.__tmp_originDescription.attribute
            ]
            if self.__tmp_originDescription.attribute == "full_name":
                types.append(Typing.BuiltinType("(string, string)"))
            self.__type = Typing.UnionType(types, None, None, None)
            self.__orig = self.__tmp_originDescription.attribute
        else:
            self.__type = typesRepo.get(self.__tmp_typeDescription)
            self.__orig = None
        del self.__tmp_typeDescription
        del self.__tmp_originDescription

    def _propagate(self):
        pass

    def _finalize(self):
        pass

    @property
    def name(self):
        return self.__name

    @property
    def type(self):
        return self.__type

    @property
    def orig(self):
        return self.__orig

    @property
    def optional(self):
        return self.__optional


class Definition(object):
    """
    At this level, all is cross-referenced. Strings are only used for string-ish data.
    Only one object represents each conceptual object.
    """
    def __init__(self, definition):
        self.__endPoints = sorted((EndPoint(*ep) for ep in definition.endPoints), key=lambda ep: (ep.url, ep.verb))
        self.__classes = sorted((Class("PyGithub.Blocking." + c.name, *c) for c in definition.classes), key=lambda c: c.name)

        endPointsRepo = {ep.verb + " " + ep.url: ep for ep in self.__endPoints}

        build = Structured.Method("Build", [], [], Structured.EndPointValue(), [], [], [], [], None, Structured.ScalarType("Github"))
        self.__builder = Class("Builder", "Builder", False, None, [], [], [build], [])

        typesRepo = Typing.Repository()
        for t in ["int", "bool", "string", "datetime", "list", "dict"]:
            typesRepo.register(Typing.BuiltinType(t))
        for t in ["Reset", "(string, string)", "GitAuthor"]:  # @todoAlpha Fix this: those are not builtins
            typesRepo.register(Typing.BuiltinType(t))
        for t in ["SessionedGithubObject", "UpdatableGithubObject", "PaginatedList"]:
            typesRepo.register(Class("PyGithub.Blocking.BaseGithubObject", t, False, None, [], [], [], []))
        for c in self.__classes:
            typesRepo.register(c)
            for s in c.structures:
                typesRepo.register(s)

        self._reference(typesRepo, endPointsRepo)
        self._propagate()
        self._finalize()

    def _reference(self, typesRepo, endPointsRepo):
        for c in self.__classes:
            c._reference(typesRepo, endPointsRepo)

        self.__builder._reference(typesRepo, endPointsRepo)

        for ep in self.__endPoints:
            ep._reference(typesRepo, endPointsRepo)

    def _propagate(self):
        for c in self.__classes:
            c._propagate()

        self.__builder._propagate()

        for ep in self.__endPoints:
            ep._propagate()

    def _finalize(self):
        for c in self.__classes:
            c._finalize()

        self.__builder._finalize()

        for ep in self.__endPoints:
            ep._finalize()

    @property
    def classes(self):
        return self.__classes

    @property
    def endPoints(self):
        return self.__endPoints
