# -*- coding: utf-8 -*-

# Copyright 2018, IBM.
#
# This source code is licensed under the Apache License, Version 2.0 found in
# the LICENSE.txt file in the root directory of this source tree.

"""Fields to be used with Qiskit validated classes."""

from functools import partial

from marshmallow import ValidationError
from marshmallow_polyfield import PolyField


class BasePolyField(PolyField):
    """Base class for polymorphic fields.

    Defines a Field that can contain data of different types. Deciding the
    type is performed by the ``to_dict_selector()`` and ``from_dict_selector()``
    functions, that act on ``choices``. Subclasses are recommended to:

    * define the type of the ``choices`` attribute. It should contain a
      reference to the individual Schemas that are accepted by the field, along
      with other information specific to the subclass.
    * customize the ``to_dict_selector()`` and ``from_dict_selector()``, adding
      the necessary logic for inspecting ``choices`` and the data, and
      returning one of the Schemas.

     Args:
        choices (iterable): iterable containing the schema instances and the
            information needed for performing disambiguation.
        many (bool): whether the field is a collection of objects.
        metadata (dict): the same keyword arguments that ``PolyField`` receives.
    """

    def __init__(self, choices, many=False, **metadata):
        to_dict_selector = partial(self.to_dict_selector, choices)
        from_dict_selector = partial(self.from_dict_selector, choices)

        super().__init__(to_dict_selector, from_dict_selector, many=many, **metadata)

    def to_dict_selector(self, choices, *args, **kwargs):
        """Return an schema in `choices` for serialization."""
        raise NotImplementedError

    def from_dict_selector(self, choices, *args, **kwargs):
        """Return an schema in `choices` for deserialization."""
        raise NotImplementedError

    def _deserialize(self, value, attr, data):
        """Override _deserialize for customizing the Exception raised."""
        try:
            return super()._deserialize(value, attr, data)
        except ValidationError as ex:
            if 'deserialization_schema_selector' in ex.messages[0]:
                ex.messages[0] = 'Cannot find a valid schema among the choices'
            raise

    def _serialize(self, value, key, obj):
        """Override _serialize for customizing the Exception raised."""
        try:
            return super()._serialize(value, key, obj)
        except TypeError as ex:
            if 'serialization_schema_selector' in str(ex):
                raise ValidationError('Data from an invalid schema')
            raise


class TryFrom(BasePolyField):
    """Polymorphic field that returns the first candidate schema that matches.

    Polymorphic field that accepts a list of candidate schemas, and iterates
    through them, returning the first Schema that matches the data. Note that
    the list of choices is traversed in order, and an attempt to match the
    data is performed until a valid Schema is found, which might have
    performance implications.

    Examples:
        class PetOwnerSchema(BaseSchema):
            pet = TryFrom([CatSchema, DogSchema])

    Args:
        choices (list[class]): list of BaseSchema classes that are iterated in
            order for for performing disambiguation.
        many (bool): whether the field is a collection of objects.
        metadata (dict): the same keyword arguments that ``PolyField`` receives.
    """

    def to_dict_selector(self, choices, base_object, *_):
        # pylint: disable=arguments-differ
        if getattr(base_object, 'schema'):
            if base_object.schema.__class__ in choices:
                return base_object.schema

        return None

    def from_dict_selector(self, choices, base_dict, *_):
        # pylint: disable=arguments-differ
        for schema_cls in choices:
            try:
                schema = schema_cls(strict=True)
                schema.load(base_dict)

                return schema_cls()
            except ValidationError:
                pass
        return None


class ByAttribute(BasePolyField):
    """Polymorphic field that disambiguates based on an attribute's existence.

    Polymorphic field that accepts a dictionary of (``'attribute': schema``)
    entries, and checks for the existence of ``attribute`` in the data for
    disambiguating.

    Examples:
        class PetOwnerSchema(BaseSchema):
            pet = ByAttribute({'fur_density': CatSchema,
                               'barking_power': DogSchema)}

    Args:
        choices (dict[string: class]): dictionary with attribute names as
            keys, and BaseSchema classes as values.
        many (bool): whether the field is a collection of objects.
        metadata (dict): the same keyword arguments that ``PolyField`` receives.
    """

    def to_dict_selector(self, choices, base_object, *_):
        # pylint: disable=arguments-differ
        if getattr(base_object, 'schema'):
            if base_object.schema.__class__ in choices.values():
                return base_object.schema

        return None

    def from_dict_selector(self, choices, base_dict, *_):
        # pylint: disable=arguments-differ
        for attribute, schema_cls in choices.items():
            if attribute in base_dict:
                return schema_cls()

        return None
