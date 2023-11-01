from pathlib import Path
from typing import ContextManager, Dict, Iterator, List, Optional

import re
import urllib.parse

from ..manifest import ManifestGenerator
from ..node_headers import NodeHeaders
from ..package import GitSource, Package
from .special import SpecialSourceProvider

_GIT_SCHEMES: Dict[str, Dict[str, str]] = {
    'github': {'scheme': 'https', 'netloc': 'github.com'},
    'gitlab': {'scheme': 'https', 'netloc': 'gitlab.com'},
    'bitbucket': {'scheme': 'https', 'netloc': 'bitbucket.com'},
    'git': {},
    'git+http': {'scheme': 'http'},
    'git+https': {'scheme': 'https'},
    'git+ssh': {'scheme': 'https'},
}


class LockfileProvider:
    # TODO: Why is from_ allowed to be optional when its asserts no none in
    # npm.py:459?
    def parse_git_source(self, version: str, from_: Optional[str] = None) -> GitSource:
        # https://github.com/microsoft/pyright/issues/1589
        # pyright: reportPrivateUsage=false

        original_url = urllib.parse.urlparse(version)
        assert original_url.scheme and original_url.path and original_url.fragment

        replacements = _GIT_SCHEMES.get(original_url.scheme, {})
        new_url = original_url._replace(fragment='', **replacements)
        # Replace e.g. git:github.com/owner/repo with git://github.com/owner/repo
        if not new_url.netloc:
            path = new_url.path.split('/')
            new_url = new_url._replace(netloc=path[0], path='/'.join(path[1:]))
        # Replace https://git@github.com:ianstormtaylor/to-camel-case.git
        # wth     https://git@github.com/ianstormtaylor/to-camel-case.git
        # effects git+ssh URLs
        if ":" in new_url.netloc:
            netloc_split = new_url.netloc.split(":")
            new_url = new_url._replace(netloc=netloc_split[0],
                                       path=f"/{netloc_split[1]}{new_url.path}")


        # TODO: if from_ is empty we have to populate it by decoding version
        # Need to get to e.g. https://git@github.com/supershabam/nop.git
        # from version=git+https://git@github.com/supershabam/nop.git#f110e75f62cfe3bf4468ac3b74e3dc72ab9ae4bf
        #if from_ is None:
            # For packagelock v3 there is no 'from' field. Instead we must
            # generate the right value.

            # Two versions, depending on whether we have a commit hash or not
            #print(f"FRAMGE {original_url.fragment}")
            #if original_url.fragment:
            #    from_ = version
            #else:
            #    from_ = "git+" + new_url.geturl()
            #print(f"HAHAHAHA {from_}")

        return GitSource(
            original=original_url.geturl(),
            url=new_url.geturl(),
            commit=original_url.fragment,
            from_=from_,
        )

    def process_lockfile(self, lockfile: Path) -> Iterator[Package]:
        raise NotImplementedError()


class RCFileProvider:
    RCFILE_NAME: str

    def parse_rcfile(self, rcfile: Path) -> Dict[str, str]:
        with open(rcfile, 'r') as r:
            rcfile_text = r.read()
        parser_re = re.compile(
            r'^(?!#|;)(\S+)(?:\s+|\s*=\s*)(?:"(.+)"|(\S+))$', re.MULTILINE
        )
        result: Dict[str, str] = {}
        for key, quoted_val, val in parser_re.findall(rcfile_text):
            result[key] = quoted_val or val
        return result

    def get_node_headers(self, rcfile: Path) -> Optional[NodeHeaders]:
        rc_data = self.parse_rcfile(rcfile)
        if 'target' not in rc_data:
            return None
        target = rc_data['target']
        runtime = rc_data.get('runtime')
        disturl = rc_data.get('disturl')

        assert isinstance(runtime, str) and isinstance(disturl, str)

        return NodeHeaders.with_defaults(target, runtime, disturl)


class ModuleProvider(ContextManager['ModuleProvider']):
    async def generate_package(self, package: Package) -> None:
        raise NotImplementedError()


class ProviderFactory:
    def create_lockfile_provider(self) -> LockfileProvider:
        raise NotImplementedError()

    def create_rcfile_providers(self) -> List[RCFileProvider]:
        raise NotImplementedError()

    def create_module_provider(
        self, gen: ManifestGenerator, special: SpecialSourceProvider
    ) -> ModuleProvider:
        raise NotImplementedError()
