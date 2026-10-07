from pathlib import Path

import footystreams
from footystreams.tools.architecture.checker import check_tree


def test_source_tree__respects_layering_purity_and_size_rules() -> None:
    package_root = Path(footystreams.__file__).parent

    violations = check_tree(package_root)

    assert not violations, "\n" + "\n".join(str(violation) for violation in violations)
