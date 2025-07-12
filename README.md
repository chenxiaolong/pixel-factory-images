# pixel-factory-images

pixel-factory-images is a small script to fetch the metadata of Google Pixel factory images from https://flash.android.com/.

It is useful for retrieving the URL of factory images that are public, but not documented, like Android Canary factory images.

### Usage

First, install `uv` or manually set up a Python virtualenv. To filter the output, also install `jq`.

Then, substitute `${codename}` in the commands below with the device codename (eg. `komodo` for Pixel 9 Pro XL).

To list all factory images:

```bash
uv run pixel-factory-images.py -d "${codename}"
```

To show the latest stable factory image:

```bash
uv run pixel-factory-images.py -d "${codename}" | jq "last(.${codename}[] | select(.latest_in_category))"
```

To show the latest beta/canary factory image:

```bash
uv run pixel-factory-images.py -d "${codename}" | jq "last(.${codename}_beta[] | select(.latest_in_category))"
```

To get just the URL of the latest stable factory image:

```bash
uv run pixel-factory-images.py -d "${codename}" | jq -r "last(.${codename}[] | select(.latest_in_category)).url"
```

To show the raw response from Google's API endpoint:

```bash
uv run pixel-factory-images.py -d "${codename}" -r
```

To include generic (non-device-specific) GSI images in the results:

```bash
uv run pixel-factory-images.py -d "${codename}" -g
```

## License

pixel-factory-images is licensed under GPLv3. Please see [`LICENSE`](./LICENSE) for the full license text.
