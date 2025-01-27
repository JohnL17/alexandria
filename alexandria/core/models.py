import re
import uuid

from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from localized_fields.fields import LocalizedCharField, LocalizedTextField

from .storage_clients import client


def make_uuid():
    """Return a new random UUID value.

    This indirection is done for testing purposes, so test code can mock
    uuid.uuid4(). If we wouldn't do this, then the models would have a direct
    reference that doesn't get mocked away.

    We can't replace it with a lambda because Django Migrations can't handle them.
    """
    return uuid.uuid4()


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_by_user = models.CharField(
        _("created by user"), max_length=150, blank=True, null=True
    )
    created_by_group = models.CharField(
        _("created by group"), max_length=255, blank=True, null=True
    )
    modified_at = models.DateTimeField(auto_now=True, db_index=True)
    modified_by_user = models.CharField(
        _("created by user"), max_length=150, blank=True, null=True
    )
    modified_by_group = models.CharField(
        _("created by group"), max_length=255, blank=True, null=True
    )
    metainfo = models.JSONField(_("metainfo"), default=dict)

    class Meta:
        abstract = True


class UUIDModel(BaseModel):
    """
    Models which use uuid as primary key.

    Defined as alexandria default
    """

    id = models.UUIDField(primary_key=True, default=make_uuid, editable=False)

    class Meta:
        abstract = True


class SlugModel(BaseModel):
    """
    Models which use a slug as primary key.

    Defined as alexandria default for configuration so it is possible
    to merge between developer and user configuration.
    """

    slug = models.SlugField(max_length=255, primary_key=True)

    class Meta:
        abstract = True


COLOR_RE = re.compile("^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$")
color_validator = RegexValidator(COLOR_RE, _("Enter a valid color."), "invalid")


class Category(SlugModel):
    name = LocalizedCharField(
        _("category name"), blank=False, null=False, required=False
    )
    description = LocalizedTextField(
        _("category description"), null=True, blank=True, required=False
    )
    color = models.CharField(
        max_length=18,
        default="#FFFFFF",
        validators=[color_validator],
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="children",
    )


class TagSynonymGroup(BaseModel):
    pass


class Tag(SlugModel):
    name = models.CharField(_("tag name"), blank=False, null=False, max_length=100)
    description = LocalizedTextField(
        _("tag description"), null=True, blank=True, required=False
    )
    tag_synonym_group = models.ForeignKey(
        TagSynonymGroup,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="tags",
    )


class Mark(SlugModel):
    name = LocalizedTextField(_("Mark name"), blank=False, null=False, max_length=100)
    description = LocalizedTextField(
        _("Mark description"), null=True, blank=True, required=False
    )


class Document(UUIDModel):
    title = LocalizedCharField(
        _("document title"), blank=True, null=True, required=False
    )
    description = LocalizedTextField(
        _("document description"), null=True, blank=True, required=False
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="documents")
    marks = models.ManyToManyField(Mark, blank=True, related_name="documents")
    date = models.DateField(blank=True, null=True)


class File(UUIDModel):
    ORIGINAL = "original"
    THUMBNAIL = "thumbnail"

    VARIANT_CHOICES = (
        ORIGINAL,
        THUMBNAIL,
    )
    VARIANT_CHOICES_TUPLE = (
        (variant_choice, variant_choice) for variant_choice in VARIANT_CHOICES
    )
    variant = models.CharField(
        choices=VARIANT_CHOICES_TUPLE, max_length=23, default=ORIGINAL
    )
    original = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="renderings",
    )
    name = models.CharField(_("file name"), max_length=255)
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="files"
    )
    checksum = models.CharField(_("checksum"), max_length=255, null=True, blank=True)

    UNDEFINED = "undefined"
    COMPLETED = "completed"
    ERROR = "error"

    STATUS_CHOICES = (
        UNDEFINED,
        COMPLETED,
        ERROR,
    )
    UPLOAD_STATUS_TUPLE = tuple(
        [(status_choice, status_choice) for status_choice in STATUS_CHOICES]
    )
    upload_status = models.CharField(
        choices=UPLOAD_STATUS_TUPLE, max_length=32, default=UNDEFINED
    )

    class Meta:
        ordering = ["-created_at"]

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        client.remove_object(self.object_name)

    @property
    def object_name(self):
        return f"{self.pk}_{self.name}"

    @property
    def upload_url(self):
        return client.upload_url(self.object_name)

    @property
    def download_url(self):
        return client.download_url(self.object_name)
