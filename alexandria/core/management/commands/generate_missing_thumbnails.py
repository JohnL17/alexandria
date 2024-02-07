from django.core.management.base import BaseCommand
from psutil import virtual_memory
from tqdm import tqdm

from alexandria.core.models import File
from alexandria.core.utils import create_thumbnail


class Command(BaseCommand):
    help = "Finds documents that don't have a thumbnail and generates them."

    def handle(self, *args, **options):
        for file in tqdm(
            File.objects.filter(variant="original", renderings__isnull=True)
        ):
            create_thumbnail(file)
            if virtual_memory().available < 300000000:
                print("about to run out of memory, stopping")
                break