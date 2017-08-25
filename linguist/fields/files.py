import six
from django.core.files.base import File
from django.db.models.fields.files import FieldFile

from . import TranslationDescriptor


class FileTranslationDescriptor(TranslationDescriptor):
    def __get__(self, instance, instance_type=None):
        file_value = result = super(FileTranslationDescriptor, self).__get__(instance, instance_type=instance_type)

        # If this value is a string (instance.file = "path/to/file") or None
        # then we simply wrap it with the appropriate attribute class according
        # to the file field. [This is FieldFile for FileFields and
        # ImageFieldFile for ImageFields; it's also conceivable that user
        # subclasses might also want to subclass the attribute class]. This
        # object understands how to convert a path to a file, and also how to
        # handle None.
        if isinstance(file_value, six.string_types) or file_value is None:
            result = self.field.attr_class(instance, self.field, file_value)

        # Other types of files may be assigned as well, but they need to have
        # the FieldFile interface added to them. Thus, we wrap any other type of
        # File inside a FieldFile (well, the field's attr_class, which is
        # usually FieldFile).
        elif isinstance(file_value, File) and not isinstance(file_value, FieldFile):
            result = self.field.attr_class(instance, self.field, file_value.name)
            result.file = file_value
            result._committed = False

        # Finally, because of the (some would say boneheaded) way pickle works,
        # the underlying FieldFile might not actually itself have an associated
        # file. So we need to reset the details of the FieldFile in those cases.
        elif isinstance(file_value, FieldFile) and not hasattr(file_value, 'field'):
            result.field = self.field
            result.storage = self.field.storage

        result.instance = instance

        super(FileTranslationDescriptor, self).__set__(instance, result)

        return result


# TODO: Needs a better implementation
# In order to support storing image dimensions in linguist,
# we would have to allow for a width and a height field for every language
# (the simpler option would be storing 'metadata' for each field,
# but the rewiring of django's internal code will be worse).

# For now, an to keep things simple, ImageTranslationFields will use the FileTranslationDescriptor.
# We can revisit this when the need arises or when we find a solid implementation.

# class ImageFileTranslationDescriptor(FileTranslationDescriptor):
#     """
#     Lifted from Django's ImageFileDescriptor
#     """
#     def __set__(self, instance, value):
#         previous_file = super(ImageFileTranslationDescriptor, self).__get__(instance, instance_type=instance.__class__)
#         super(ImageFileTranslationDescriptor, self).__set__(instance, value)
#
#         if previous_file is not None:
#             self.field.update_dimension_fields(instance, force=True)
