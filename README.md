[![Tests](https://github.com/open-data/ckanext-language-domains/workflows/Tests/badge.svg?branch=main)](https://github.com/open-data/ckanext-language-domains/actions)

# CKANEXT Language Domains

This plugin hooks into various parts of the CKAN framework to allow for vanity language domains. It forces CKAN to no longer use language sub-directories, redirecting requested sub-directories to their mapped domain name.

It is not required to use different languages with this plugin, you could use it to have multiple vanity domains for your CKAN install. This plugin supports `ckan.root_path` as well with a config option `ckanext.language_domains.root_paths`.

## Requirements

Compatibility with core CKAN versions:

| CKAN version    | Compatible?   |
| --------------- | ------------- |
| 2.6 and earlier | no    |
| 2.7             | no    |
| 2.8             | no    |
| 2.9             | no    |
| 2.10             | yes    |
| 2.11             | yes    |

Compatibility with Python versions:

| Python version    | Compatible?   |
| --------------- | ------------- |
| 2.7 and earlier | no    |
| 3.7 and later            | yes    |

## Installation

To install ckanext-language-domains:

1. Activate your CKAN virtual environment, for example:

     . /usr/lib/ckan/default/bin/activate

2. Clone the source and install it on the virtualenv:
  ```
  git clone https://github.com/open-data/ckanext-language-domains.git
  cd ckanext-language-domains
  pip install -e .
  ```
3. Add `language_domains` to the `ckan.plugins` setting in your CKAN
   config file (by default the config file is located at
   `/etc/ckan/default/ckan.ini`) to *__the very top of the list__*.

4. Restart CKAN. For example if you've deployed CKAN with Apache on Ubuntu:

     sudo service apache2 reload

## Config settings

**ckanext.language_domains.secret** specifies the secret for JWT token encoding and decoding. This is used for authenticating login sessions across domains:

	# (required, default: None).
	ckanext.language_domains.secret = thisisalegitsecret

**ckanext.language_domains.domain_map** specifies a mapping of languages to domains:

	# (required, default: None).
	ckanext.language_domains.domain_map = {
      "en": ["example.com", "example2.ca"],
      "fr": ["exemple.com", "exempledeux.ca"]}

  The plugin will redirect requests based on the requested domain and the order in the mapped lists. E.g. from the example above, if a user requested `https://example2.ca/fr/page` they would be redirected to `https://exempledeux.ca/page`

**ckanext.language_domains.root_paths** specifies a mapping of domains and their root paths:

  # (optional, default: None).
	ckanext.language_domains.root_paths = {
      "example.com": "/data/{{LANG}}",
      "exemple.com": "/data/{{LANG}}"}