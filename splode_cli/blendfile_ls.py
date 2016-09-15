#!/usr/bin/env python3

"""Lists datablocks in blend-files."""

import argparse
import logging

from bam.blend import blendfile

log = logging.getLogger(__name__)


def list_datablocks(bfile: blendfile.BlendFile):
    log.info('Datablocks:')

    libraries = {}

    for idx, block in enumerate(bfile.blocks):

        if block.dna_type_name == 'Library':
            libraries[block.addr_old] = block

        info = ['%4i: %-15s' % (idx, block.dna_type_name)]

        block_name = block.get(b'name', None)
        if block_name:
            info.append('name=%r' % block_name)

        try:
            id_name = block.get((b'id', b'name'))
        except KeyError:
            pass
        except UnicodeDecodeError:
            pass
        else:
            info.append('id.name=%r' % id_name)

        lib_addr = block.get(b'lib', None)
        if lib_addr:
            from_lib = libraries[lib_addr]
            lib_name = from_lib.get(b'name')
            info.append('@%s' % lib_name)

        log.info(' '.join(info))

        # for key, value in block.items():
        #     log.info('    %s = %r', key, value)
        # try:
        #     for path, thingy in block.get_recursive_iter(b'id'):
        #         log.info('    %r = %r', path, thingy)
        # except KeyError:
        #     pass


def list_structs(bfile: blendfile.BlendFile):
    log.info('Structs:')
    for idx, struct in enumerate(bfile.structs):
        log.info('%4i: %s', idx, struct)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='Input blend-file')
    parser.add_argument(
        '-q', '--quiet', dest='use_quiet', action='store_true', required=False,
        help='Suppress status output')
    args = parser.parse_args()

    # Configure logging
    if args.use_quiet:
        loglevel = logging.WARNING
    else:
        loglevel = logging.INFO
    logging.basicConfig(level=loglevel,
                        format='%(asctime)-15s %(levelname)8s %(name)s %(message)s')

    log.info('Starting listing of %s', args.input)

    with blendfile.open_blend(args.input) as bfile:
        list_datablocks(bfile)
        # list_structs(bfile)


if __name__ == '__main__':
    main()
