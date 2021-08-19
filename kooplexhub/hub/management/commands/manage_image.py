import logging

from django.core.management.base import BaseCommand, CommandError
from hub.models import Image, Proxy, EnvVarMapping

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Manage images'

    def add_arguments(self, parser):
        parser.add_argument('--add', help = "Add image", nargs = 1)
        parser.add_argument('--add_proxy', help = "Add Proxy", nargs = 7)
        parser.add_argument('--add_envvar', help = "Add Proxy", nargs = 3)
        parser.add_argument('--remove', help = "Remove image", nargs = 1)
        parser.add_argument('--remove_proxy', help = "Remove Proxy", nargs = 1)
        parser.add_argument('--remove_envvar', help = "Remove Proxy", nargs = 1)
    
    def handle(self, *args, **options):
        logger.info("call %s %s" % (args, options))
        add_image = options.get('add')
        add_proxy = options.get('add_proxy')
        add_envvar = options.get('add_envvar')
        remove_image = options.get('remove')
        remove_proxy = options.get('remove_proxy')
        remove_envvar = options.get('remove_envvar')
        if add_image:
            i, s = Image.objects.get_or_create(name = add_image.pop())
            logger.info('Image %s %s' % (i, 'created' if s else 'exists'))
        if remove_image:
            try:
                i = Image.objects.get(name = remove_image.pop())
                i.delete()
                logger.info('Removed image %s' % i.name)
            except Image.DoesNotExist:
                pass
        if add_proxy:
            print(add_proxy)
            port = add_proxy.pop()
            path_open = add_proxy.pop(),
            path = add_proxy.pop()
            token_as_argument = add_proxy.pop()
            default = add_proxy.pop()
            image_name = add_proxy.pop()
            image = Image.objects.get(name = image_name) 
            name = add_proxy.pop()
            print(name, image , default, token_as_argument, path, path_open, port)
            i, s = Proxy.objects.get_or_create(name = name, image = image, default = default, token_as_argument = token_as_argument, path=path, path_open = path_open, port=port)
            logger.info('Proxy %s %s' % (i, 'created' if s else 'exists'))
        if add_envvar:
            print(add_envvar)
            valuemap = add_envvar.pop()
            name = add_envvar.pop()
            image_name = add_envvar.pop()
            image = Image.objects.get(name = image_name) 
            print(image, name, valuemap)
            i, s = EnvVarMapping.objects.get_or_create(name = name, image = image, valuemap = valuemap)
            logger.info('EnvVarMapping %s %s' % (i, 'created' if s else 'exists'))

