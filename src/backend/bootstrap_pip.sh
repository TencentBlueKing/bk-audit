#!/bin/sh
# Python's CA incident recovery wheel; keep URL and SHA256 together when updating.
# https://discuss.python.org/t/109576
set -eu

python_bin=${1:-python}
wheel_dir=${2:-}
if [ -z "$wheel_dir" ]; then
    wheel_dir=$(mktemp -d)
    trap 'rm -rf "$wheel_dir"' EXIT
fi
mkdir -p "$wheel_dir"
bootstrap_url='https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70'
"$python_bin" -m pip --isolated --disable-pip-version-check download --no-index --no-deps --no-cache-dir --dest "$wheel_dir" "$bootstrap_url"
"$python_bin" -m pip --isolated --disable-pip-version-check install --no-index --no-deps "$wheel_dir/pip-26.2.2-py3-none-any.whl"

# The patched pip bundle does not repair an outdated OS trust store.
"$python_bin" -c 'import hashlib, ssl, sys; rejected = "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b"; roots = ssl.create_default_context().get_ca_certs(binary_form=True); sys.exit("OS still trusts emSign ECC Root CA - G3; update the official OS/base image certificates before installing dependencies") if any(hashlib.sha256(root).hexdigest() == rejected for root in roots) else None'
