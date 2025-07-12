#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2025 Andrew Gunnerson
# SPDX-License-Identifier: GPL-3.0-only

import argparse
import dataclasses
import json
import re
import sys
from typing import Any

import bs4
import requests


RE_VAR = re.compile(r'\${[a-zA-Z0-9_]+}')
RE_DENY = re.compile(r'^(\${[a-z]+}(ms|px)?|directive_chipid_\${[a-z]+})$')
RE_GSI = re.compile(r'^(.*_)?(arm(64)?|aarch64)(_.*)?$')


def get_candidate_product(codename: str, gsi: bool, candidate: str) -> str | None:
    # Eg. ${h}ms, directive_chipid_${d}
    if RE_DENY.match(candidate):
        return None

    # Eg. ${d}_fullmte
    replaced, matches = RE_VAR.subn(codename, candidate)
    if matches == 1:
        return replaced

    # Eg. aosp_komodo_16k, komodo_16k
    if codename in candidate and '_' in candidate:
        return candidate

    # Eg. aosp_arm64_pubsign, kernel_aarch64
    if gsi and RE_GSI.match(candidate):
        return candidate

    return None


@dataclasses.dataclass
class LookupOptions:
    api_key: str
    products: set[str]


RE_API_KEY = re.compile(r'^"([a-zA-Z0-9-_]{39})"$')


def get_lookup_options(codename: str, gsi: bool) -> LookupOptions:
    # We only pass in the user agent so that Google doesn't serve the ECMAScript
    # 5 version of the minified JS. With the user agent, we get the ECMAScript
    # 2018 version, which uses easier-to-match interpolated strings.
    r = requests.get(
        'https://flash.android.com/',
        headers={'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'},
    )
    r.raise_for_status()

    html = bs4.BeautifulSoup(r.text, 'html.parser')

    # Fetch the API key.
    body = html.find('body')
    if not body:
        raise ValueError(f'Missing <body>: {html}')

    client_config = body.get('data-client-config')
    if not client_config:
        raise ValueError(f'Missing client config: {body}')

    for s in client_config.split(','):
        match = RE_API_KEY.match(s)
        if match:
            api_key = match.group(1)
            break
    else:
        raise ValueError(f'API key not found: {client_config}')

    # Fetch the set of probable product IDs.
    script = html.find('link', attrs={'as': 'script'})
    if not script:
        raise ValueError(f'JS script not found: {html}')

    r = requests.get(script['href'])
    r.raise_for_status()

    strings = re.findall(r'["`]([a-z0-9\$][a-z0-9_\${}]*)["`]', r.text)
    products = set()

    for string in strings:
        candidate = get_candidate_product(codename, gsi, string)
        if candidate:
            products.add(candidate)

    # The codename itself is always valid.
    products.add(codename)

    return LookupOptions(api_key, products)


def fetch_metadata(options: LookupOptions) -> dict[str, Any]:
    # The actual site uses the /batch endpoint, but we don't need that for a
    # single API call.
    r = requests.get(
        'https://content-flashstation-pa.googleapis.com/v1/builds',
        headers={'referer': 'https://flash.android.com/'},
        params={
            'key': options.api_key,
            'product': sorted(options.products),
        },
    )
    r.raise_for_status()

    return r.json()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-d', '--device',
        required=True,
        help='Device codename',
    )
    parser.add_argument(
        '-g', '--gsi',
        action='store_true',
        help='Include generic GSI images',
    )
    parser.add_argument(
        '-r', '--raw',
        action='store_true',
        help='Show raw response from server',
    )

    return parser.parse_args()


def main():
    args = parse_args()

    options = get_lookup_options(args.device, args.gsi)
    metadata = fetch_metadata(options)

    if args.raw:
        json.dump(metadata, sys.stdout, indent=4)
    else:
        builds = metadata.get('flashstationBuild', [])
        builds.sort(key=lambda b: int(b['buildId']))

        by_product = {}

        for build in builds:
            version_name = None

            if 'versionName' in build:
                version_name = build['versionName']
            elif 'previewMetadata' in build:
                version_name = build['previewMetadata']['releaseTrackName'] + \
                    ' - ' + build['previewMetadata']['releaseTrackVersionName']
            else:
                version_name = None

            if 'releaseBuildMetadata' in build:
                latest = build['releaseBuildMetadata']['latest']
            elif 'previewMetadata' in build:
                latest = build['previewMetadata']['active']
            else:
                latest = False

            if 'releaseBuildMetadata' in build:
                description = build['releaseBuildMetadata']['notes'] or None
            else:
                description = None

            by_product.setdefault(build['product'], []).append({
                'name': build['releaseCandidateName'],
                'description': description,
                'latest_in_category': latest,
                'version': version_name,
                'url': build['factoryImageDownloadUrl'],
            })

        json.dump(by_product, sys.stdout, indent=4)

    print()


if __name__ == '__main__':
    main()
