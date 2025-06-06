"""EOF Subcontainer tests covering simple cases."""

import pytest

from ethereum_test_tools import Account, EOFException, EOFStateTestFiller, EOFTestFiller
from ethereum_test_tools.vm.opcode import Opcodes as Op
from ethereum_test_types.eof.v1 import Container, ContainerKind, Section
from ethereum_test_types.eof.v1.constants import MAX_BYTECODE_SIZE, MAX_INITCODE_SIZE
from ethereum_test_vm import Bytecode

from .. import EOF_FORK_NAME
from .helpers import slot_code_worked, value_code_worked

REFERENCE_SPEC_GIT_PATH = "EIPS/eip-7620.md"
REFERENCE_SPEC_VERSION = "52ddbcdddcf72dd72427c319f2beddeb468e1737"

pytestmark = pytest.mark.valid_from(EOF_FORK_NAME)

eofcreate_code_section = Section.Code(
    code=Op.EOFCREATE[0](0, 0, 0, 0) + Op.SSTORE(slot_code_worked, value_code_worked) + Op.STOP,
    max_stack_height=4,
)
eofcreate_revert_code_section = Section.Code(
    code=Op.EOFCREATE[0](0, 0, 0, 0) + Op.REVERT(0, 0),
)
returncode_code_section = Section.Code(
    code=Op.SSTORE(slot_code_worked, value_code_worked) + Op.RETURNCODE[0](0, 0),
    max_stack_height=2,
)
stop_container = Container.Code(Op.STOP)
stop_sub_container = Section.Container(stop_container)
return_sub_container = Section.Container(Container.Code(Op.RETURN(0, 0)))
revert_sub_container = Section.Container(Container.Code(Op.REVERT(0, 0)))
abort_sub_container = Section.Container(Container.Code(Op.INVALID))
returncode_sub_container = Section.Container(
    Container(
        sections=[
            Section.Code(Op.RETURNCODE[0](0, 0)),
            stop_sub_container,
        ],
    )
)


def test_simple_create_from_deployed(
    eof_state_test: EOFStateTestFiller,
):
    """Simple EOF creation from a deployed EOF container."""
    eof_state_test(
        container=Container(
            sections=[
                eofcreate_code_section,
                returncode_sub_container,
            ],
        ),
        container_post=Account(storage={slot_code_worked: value_code_worked}),
    )


def test_simple_create_from_creation(
    eof_state_test: EOFStateTestFiller,
):
    """Simple EOF creation from a create transaction container."""
    eof_state_test(
        container=Container(
            sections=[
                returncode_code_section,
                stop_sub_container,
            ],
            kind=ContainerKind.INITCODE,
        ),
        container_post=Account(storage={slot_code_worked: value_code_worked}),
    )


@pytest.mark.parametrize(
    "zero_section",
    [eofcreate_code_section, returncode_code_section],
    ids=["eofcreate", "returncode"],
)
def test_reverting_container(
    eof_state_test: EOFStateTestFiller,
    zero_section: Container,
):
    """Test revert containers."""
    eof_state_test(
        container=Container(
            sections=[
                zero_section,
                revert_sub_container,
            ],
            kind=(
                ContainerKind.INITCODE
                if zero_section == returncode_code_section
                else ContainerKind.RUNTIME
            ),
        ),
        container_post=Account(storage={slot_code_worked: value_code_worked}),
    )


@pytest.mark.parametrize(
    "code_section,first_sub_container,container_kind",
    [
        (eofcreate_code_section, returncode_sub_container, ContainerKind.RUNTIME),
        (returncode_code_section, stop_sub_container, ContainerKind.INITCODE),
    ],
    ids=["eofcreate", "returncode"],
)
@pytest.mark.parametrize(
    "extra_sub_container",
    [stop_sub_container, revert_sub_container, returncode_sub_container],
    ids=["stop", "revert", "returncode"],
)
def test_orphan_container(
    eof_test: EOFTestFiller,
    code_section: Section,
    first_sub_container: Container,
    extra_sub_container: Container,
    container_kind: ContainerKind,
):
    """Test orphaned containers."""
    eof_test(
        container=Container(
            sections=[
                code_section,
                first_sub_container,
                extra_sub_container,
            ],
            kind=container_kind,
        ),
        expect_exception=EOFException.ORPHAN_SUBCONTAINER,
    )


@pytest.mark.parametrize(
    "code_section,sub_container,container_kind",
    [
        pytest.param(
            eofcreate_code_section,
            returncode_sub_container,
            ContainerKind.RUNTIME,
            id="EOFCREATE_RETURNCODE",
        ),
        pytest.param(
            returncode_code_section,
            stop_sub_container,
            ContainerKind.INITCODE,
            id="RETURNCODE_STOP",
        ),
        pytest.param(
            returncode_code_section,
            return_sub_container,
            ContainerKind.INITCODE,
            id="RETURNCODE_RETURN",
        ),
        pytest.param(
            eofcreate_code_section,
            revert_sub_container,
            ContainerKind.RUNTIME,
            id="EOFCREATE_REVERT",
        ),
        pytest.param(
            returncode_code_section,
            revert_sub_container,
            ContainerKind.INITCODE,
            id="RETURNCODE_REVERT",
        ),
    ],
)
def test_container_combos_valid(
    eof_state_test: EOFStateTestFiller,
    code_section: Section,
    sub_container: Container,
    container_kind: ContainerKind,
):
    """Test valid subcontainer reference / opcode combos."""
    eof_state_test(
        container=Container(
            sections=[
                code_section,
                sub_container,
            ],
            kind=container_kind,
        ),
        container_post=Account(storage={slot_code_worked: value_code_worked}),
    )


@pytest.mark.parametrize(
    "code_section,first_sub_container,container_kind",
    [
        pytest.param(
            eofcreate_code_section,
            stop_sub_container,
            ContainerKind.RUNTIME,
            id="EOFCREATE_STOP",
        ),
        pytest.param(
            eofcreate_code_section,
            return_sub_container,
            ContainerKind.RUNTIME,
            id="EOFCREATE_RETURN",
        ),
        pytest.param(
            returncode_code_section,
            returncode_sub_container,
            ContainerKind.INITCODE,
            id="RETURNCODE_RETURNCODE",
        ),
    ],
)
def test_container_combos_invalid(
    eof_test: EOFTestFiller,
    code_section: Section,
    first_sub_container: Container,
    container_kind: ContainerKind,
):
    """Test invalid subcontainer reference / opcode combos."""
    eof_test(
        container=Container(
            sections=[
                code_section,
                first_sub_container,
            ],
            kind=container_kind,
        ),
        expect_exception=EOFException.INCOMPATIBLE_CONTAINER_KIND,
    )


@pytest.mark.parametrize(
    "code_section,first_sub_container",
    [
        pytest.param(
            eofcreate_revert_code_section,
            returncode_sub_container,
            id="EOFCREATE_RETURNCODE",
        ),
        pytest.param(
            returncode_code_section,
            stop_sub_container,
            id="RETURNCODE_STOP",
        ),
        pytest.param(
            returncode_code_section,
            return_sub_container,
            id="RETURNCODE_RETURN",
        ),
        pytest.param(
            eofcreate_revert_code_section,
            revert_sub_container,
            id="EOFCREATE_REVERT",
        ),
        pytest.param(
            returncode_code_section,
            revert_sub_container,
            id="RETURNCODE_REVERT",
        ),
    ],
)
def test_container_combos_deeply_nested_valid(
    eof_test: EOFTestFiller,
    code_section: Section,
    first_sub_container: Container,
):
    """Test valid subcontainer reference / opcode combos on a deep container nesting level."""
    valid_container = Container(
        sections=[
            code_section,
            first_sub_container,
        ],
        kind=ContainerKind.INITCODE,
    )

    container = valid_container
    while len(container) < MAX_BYTECODE_SIZE:
        container = Container(
            sections=[
                eofcreate_revert_code_section,
                Section.Container(container=container.copy()),
            ],
            kind=ContainerKind.INITCODE,
        )

    eof_test(
        container=container,
        deployed_container=None,  # Execution reverts before deployment
    )


@pytest.mark.parametrize(
    "code_section,first_sub_container",
    [
        pytest.param(
            eofcreate_revert_code_section,
            stop_sub_container,
            id="EOFCREATE_STOP",
        ),
        pytest.param(
            eofcreate_revert_code_section,
            return_sub_container,
            id="EOFCREATE_RETURN",
        ),
        pytest.param(
            returncode_code_section,
            returncode_sub_container,
            id="RETURNCODE_RETURNCODE",
        ),
    ],
)
def test_container_combos_deeply_nested_invalid(
    eof_test: EOFTestFiller,
    code_section: Section,
    first_sub_container: Container,
):
    """Test invalid subcontainer reference / opcode combos on a deep container nesting level."""
    invalid_container = Container(
        sections=[
            code_section,
            first_sub_container,
        ],
        kind=ContainerKind.INITCODE,
    )

    container = invalid_container
    while len(container) < MAX_BYTECODE_SIZE:
        container = Container(
            sections=[
                eofcreate_revert_code_section,
                Section.Container(container=container.copy()),
            ],
            kind=ContainerKind.INITCODE,
        )

    eof_test(
        container=container,
        expect_exception=EOFException.INCOMPATIBLE_CONTAINER_KIND,
    )


@pytest.mark.parametrize(
    "code_section,first_sub_container,container_kind",
    [
        pytest.param(
            eofcreate_code_section,
            returncode_sub_container,
            ContainerKind.RUNTIME,
            id="EOFCREATE_RETURNCODE",
        ),
        pytest.param(
            returncode_code_section,
            stop_sub_container,
            ContainerKind.INITCODE,
            id="RETURNCODE_STOP",
        ),
        pytest.param(
            returncode_code_section,
            return_sub_container,
            ContainerKind.INITCODE,
            id="RETURNCODE_RETURN",
        ),
        pytest.param(
            eofcreate_code_section,
            revert_sub_container,
            ContainerKind.RUNTIME,
            id="EOFCREATE_REVERT",
        ),
        pytest.param(
            returncode_code_section,
            revert_sub_container,
            ContainerKind.INITCODE,
            id="RETURNCODE_REVERT",
        ),
    ],
)
def test_container_combos_non_first_code_sections_valid(
    eof_test: EOFTestFiller,
    code_section: Section,
    first_sub_container: Container,
    container_kind: ContainerKind,
):
    """Test valid subcontainer reference / opcode combos in a non-first code section."""
    eof_test(
        container=Container(
            sections=[Section.Code(Op.JUMPF[i]) for i in range(1, 1024)]
            + [code_section, first_sub_container],
            kind=container_kind,
        ),
    )


@pytest.mark.parametrize(
    "code_section,first_sub_container,container_kind",
    [
        pytest.param(
            eofcreate_code_section,
            stop_sub_container,
            ContainerKind.RUNTIME,
            id="EOFCREATE_STOP",
        ),
        pytest.param(
            eofcreate_code_section,
            return_sub_container,
            ContainerKind.RUNTIME,
            id="EOFCREATE_RETURN",
        ),
        pytest.param(
            returncode_code_section,
            returncode_sub_container,
            ContainerKind.INITCODE,
            id="RETURNCODE_RETURNCODE",
        ),
    ],
)
def test_container_combos_non_first_code_sections_invalid(
    eof_test: EOFTestFiller,
    code_section: Section,
    first_sub_container: Container,
    container_kind: ContainerKind,
):
    """Test invalid subcontainer reference / opcode combos in a non-first code section."""
    eof_test(
        container=Container(
            sections=[Section.Code(Op.JUMPF[i]) for i in range(1, 1024)]
            + [code_section, first_sub_container],
            kind=container_kind,
        ),
        expect_exception=EOFException.INCOMPATIBLE_CONTAINER_KIND,
    )


def test_container_both_kinds_same_sub(eof_test: EOFTestFiller):
    """Test subcontainer conflicts (both EOFCREATE and RETURNCODE Reference)."""
    eof_test(
        container=Container(
            sections=[
                Section.Code(
                    code=Op.EOFCREATE[0](0, 0, 0, 0) + Op.JUMPF[1],
                ),
                Section.Code(
                    code=Op.RETURNCODE[0](0, 0),
                ),
                revert_sub_container,
            ],
        ),
        expect_exception=EOFException.INCOMPATIBLE_CONTAINER_KIND,
    )


@pytest.mark.parametrize("container_idx", [0, 1, 255])
@pytest.mark.parametrize(
    "sub_container",
    [
        pytest.param(abort_sub_container, id="abort"),
        pytest.param(revert_sub_container, id="revert"),
    ],
)
def test_container_ambiguous_kind(
    eof_test: EOFTestFiller, container_idx: int, sub_container: Section
):
    """
    Test ambiguous container kind:
    a single subcontainer reference by both EOFCREATE and RETURNCODE.
    """
    sections = [
        Section.Code(
            code=(
                sum(Op.EOFCREATE[i](0, 0, 0, 0) for i in range(container_idx))
                + Op.EOFCREATE[container_idx](0, 0, 0, 0)
                + Op.RETURNCODE[container_idx](0, 0)
            ),
        ),
    ]
    sections += (container_idx + 1) * [sub_container]

    eof_test(
        container=Container(
            sections=sections,
            kind=ContainerKind.INITCODE,
        ),
        expect_exception=EOFException.AMBIGUOUS_CONTAINER_KIND,
    )


def test_container_both_kinds_different_sub(eof_test: EOFTestFiller):
    """Test multiple kinds of subcontainer at the same level."""
    eof_test(
        container=Container(
            sections=[
                Section.Code(
                    code=Op.EOFCREATE[0](0, 0, 0, 0) + Op.JUMPF[1],
                ),
                Section.Code(
                    code=Op.RETURNCODE[1](0, 0),
                ),
                returncode_sub_container,
                stop_sub_container,
            ],
            kind=ContainerKind.INITCODE,
        ),
        deployed_container=stop_container,
    )


def test_container_multiple_eofcreate_references(eof_test: EOFTestFiller):
    """Test multiple references to the same subcontainer from an EOFCREATE operation."""
    eof_test(
        container=Container(
            sections=[
                Section.Code(
                    code=Op.EOFCREATE[0](0, 0, 0, 0) + Op.EOFCREATE[0](0, 0, 0, 0) + Op.STOP,
                ),
                returncode_sub_container,
            ],
        ),
    )


def test_container_multiple_returncode_references(eof_test: EOFTestFiller):
    """Test multiple references to the same subcontainer from a RETURNCONTACT operation."""
    eof_test(
        container=Container(
            sections=[
                Section.Code(
                    code=Op.PUSH0
                    + Op.CALLDATALOAD
                    + Op.RJUMPI[6]
                    + Op.RETURNCODE[0](0, 0)
                    + Op.RETURNCODE[0](0, 0)
                ),
                stop_sub_container,
            ],
            kind=ContainerKind.INITCODE,
        ),
    )


@pytest.mark.parametrize("version", [0, 255], ids=lambda x: x)
def test_subcontainer_wrong_eof_version(
    eof_test: EOFTestFiller,
    version: int,
):
    """Test a subcontainer with the incorrect EOF version."""
    eof_test(
        container=Container(
            sections=[
                Section.Code(
                    code=Op.EOFCREATE[0](0, 0, 0, 0) + Op.STOP,
                ),
                Section.Container(
                    container=Container(version=[version], sections=[Section.Code(code=Op.STOP)])
                ),
            ],
            kind=ContainerKind.RUNTIME,
        ),
        expect_exception=EOFException.INVALID_VERSION,
    )


@pytest.mark.parametrize("delta", [-1, 1], ids=["smaller", "larger"])
@pytest.mark.parametrize("kind", [ContainerKind.RUNTIME, ContainerKind.INITCODE])
def test_subcontainer_wrong_size(
    eof_test: EOFTestFiller,
    delta: int,
    kind: ContainerKind,
):
    """Test a subcontainer with the incorrect size in the parent's header."""
    eof_test(
        container=Container(
            sections=[
                Section.Code(
                    code=(Op.EOFCREATE[0](0, 0, 0, 0) + Op.STOP)
                    if kind == ContainerKind.RUNTIME
                    else (Op.RETURNCODE[0](0, 0)),
                ),
                Section.Container(
                    container=Container(sections=[Section.Code(code=Op.STOP)]),
                    custom_size=len(stop_sub_container.data) + delta,
                ),
            ],
            kind=kind,
        ),
        expect_exception=EOFException.INVALID_SECTION_BODIES_SIZE,
    )


deep_container_parametrize = pytest.mark.parametrize(
    ["deepest_container", "exception"],
    [
        pytest.param(Container.Code(Op.STOP), None, id="valid"),
        pytest.param(
            Container.Code(code=Op.PUSH0),
            EOFException.MISSING_STOP_OPCODE,
            id="code-error",
        ),
        pytest.param(
            Container(raw_bytes="EF0100A94F5374FCE5EDBC8E2A8697C15331677E6EBF0B"),
            EOFException.INVALID_MAGIC,
            id="structure-error",
        ),
    ],
)


@deep_container_parametrize
@pytest.mark.eof_test_only(reason="Initcontainer exceeds maximum")
def test_deep_container(
    eof_test: EOFTestFiller, deepest_container: Container, exception: EOFException | None
):
    """
    Test a very deeply nested container.

    This test skips generating a state test because the initcode size is too large.
    """
    container = deepest_container
    last_container = deepest_container
    while len(container) < MAX_INITCODE_SIZE:
        last_container = container
        container = Container(
            sections=[
                Section.Code(
                    code=Op.PUSH0 + Op.PUSH0 + Op.PUSH0 + Op.PUSH0 + Op.EOFCREATE[0] + Op.STOP,
                ),
                Section.Container(
                    container=Container(
                        sections=[
                            Section.Code(
                                code=Op.PUSH0 + Op.PUSH0 + Op.RETURNCODE[0],
                            ),
                            Section.Container(container=last_container),
                        ]
                    )
                ),
            ],
        )

    eof_test(container=last_container, expect_exception=exception)


@deep_container_parametrize
def test_deep_container_initcode(
    eof_test: EOFTestFiller, deepest_container: Container, exception: EOFException | None
):
    """Test a very deeply nested initcontainer."""
    container = Container(
        sections=[
            Section.Code(
                code=Op.PUSH0 + Op.PUSH0 + Op.RETURNCODE[0],
            ),
            Section.Container(container=deepest_container),
        ],
        kind=ContainerKind.INITCODE,
    )
    last_container = container
    while len(container) < MAX_INITCODE_SIZE:
        last_container = container
        container = Container(
            sections=[
                Section.Code(
                    code=Op.PUSH0 + Op.PUSH0 + Op.RETURNCODE[0],
                ),
                Section.Container(
                    container=Container(
                        sections=[
                            Section.Code(
                                code=Op.PUSH0
                                + Op.PUSH0
                                + Op.PUSH0
                                + Op.PUSH0
                                + Op.EOFCREATE[0]
                                + Op.STOP
                            ),
                            Section.Container(container=last_container),
                        ]
                    )
                ),
            ],
            kind=ContainerKind.INITCODE,
        )
    eof_test(
        container=last_container,
        expect_exception=exception,
        deployed_container=None,
    )


@pytest.mark.parametrize(
    ["width", "exception"],
    [
        pytest.param(256, None, id="256"),
        pytest.param(257, EOFException.TOO_MANY_CONTAINERS, id="257"),
        pytest.param(
            0x8000,
            EOFException.CONTAINER_SIZE_ABOVE_LIMIT,
            marks=pytest.mark.eof_test_only(reason="int too big to convert"),
            id="negative_i16",
        ),
        pytest.param(
            0xFFFF,
            EOFException.CONTAINER_SIZE_ABOVE_LIMIT,
            marks=pytest.mark.eof_test_only(reason="int too big to convert"),
            id="max_u16",
        ),
    ],
)
def test_wide_container(eof_test: EOFTestFiller, width: int, exception: EOFException):
    """Test a container with the maximum number of sub-containers."""
    create_code: Bytecode = Op.STOP
    for x in range(0, 256):
        create_code = Op.EOFCREATE[x](0, 0, 0, 0) + create_code
    eof_test(
        container=Container(
            sections=[
                Section.Code(
                    code=create_code,
                ),
                *(
                    [
                        Section.Container(
                            container=Container(
                                sections=[
                                    Section.Code(
                                        code=Op.PUSH0 + Op.PUSH0 + Op.RETURNCODE[0],
                                    ),
                                    stop_sub_container,
                                ]
                            )
                        )
                    ]
                    * width
                ),
            ]
        ),
        expect_exception=exception,
    )


@pytest.mark.parametrize(
    "container",
    [
        pytest.param(
            Container(
                sections=[
                    Section.Code(
                        Op.CALLDATASIZE
                        + Op.PUSH1[0]
                        + Op.PUSH1[255]
                        + Op.PUSH1[0]
                        + Op.EOFCREATE[0]
                        + Op.POP
                        + Op.STOP
                    ),
                    abort_sub_container,
                ],
                expected_bytecode="""
                ef0001010004020001000b03000100000014ff0000000080000436600060ff6000ec005000ef000101000402
                00010001ff00000000800000fe""",
            ),
            id="eofcreate_0",
        ),
        pytest.param(
            Container(
                sections=[
                    Section.Code(Op.PUSH1[0] + Op.RJUMP[0] + Op.STOP),
                    abort_sub_container,
                ],
                expected_bytecode="""
                ef0001010004020001000603000100000014ff000000008000016000e0000000ef000101000402000100
                01ff00000000800000fe""",
                # Originally this test was "valid" because it was created
                # before "orphan subcontainer" rule was introduced.
                validity_error=EOFException.ORPHAN_SUBCONTAINER,
            ),
            id="orphan_subcontainer_0",
        ),
        pytest.param(
            Container(
                sections=[
                    Section.Code(Op.PUSH1[0] + Op.RJUMP[0] + Op.STOP),
                    abort_sub_container,
                    Section.Data(custom_size=2),
                ],
                expected_bytecode="""
                ef0001010004020001000603000100000014ff000200008000016000e0000000ef000101000402000100
                01ff00000000800000fe""",
                # Originally this test was "valid" but against the current spec
                # it contains two errors: data section truncated and orphan subcontainer.
                validity_error=EOFException.TOPLEVEL_CONTAINER_TRUNCATED,
            ),
            id="orphan_subcontainer_0_and_truncated_data",
        ),
        pytest.param(
            Container(
                sections=[
                    Section.Code(Op.PUSH1[0] + Op.RJUMP[0] + Op.STOP),
                    abort_sub_container,
                    Section.Data("aabb"),
                ],
                expected_bytecode="""
                ef0001010004020001000603000100000014ff000200008000016000e0000000ef000101000402000100
                01ff00000000800000feaabb""",
                # Originally this test was "valid" because it was created
                # before "orphan subcontainer" rule was introduced.
                validity_error=EOFException.ORPHAN_SUBCONTAINER,
            ),
            id="orphan_subcontainer_0_and_data",
        ),
        pytest.param(
            Container(
                sections=[
                    Section.Code(Op.EOFCREATE[0](0, 0, 0, 0) + Op.STOP),
                    Section.Container("aabbccddeeff"),
                ],
                # The original test has been modified to reference the subcontainer by EOFCREATE.
                validity_error=EOFException.INVALID_MAGIC,
            ),
            id="subcontainer_0_with_invalid_prefix",
        ),
        pytest.param(
            Container(
                sections=[
                    Section.Code(
                        Op.CALLDATASIZE
                        + Op.PUSH1[0]
                        + Op.PUSH1[255]
                        + Op.PUSH1[0]
                        + Op.EOFCREATE[1]
                        + Op.POP
                        + Op.STOP
                    )
                ]
                + 2 * [abort_sub_container],
                expected_bytecode="""
                ef0001010004020001000b0300020000001400000014ff0000000080000436600060ff6000ec015000ef00010100
                040200010001ff00000000800000feef00010100040200010001ff00000000800000fe""",
                # Originally this test was "valid" because it was created
                # before "orphan subcontainer" rule was introduced.
                validity_error=EOFException.ORPHAN_SUBCONTAINER,
            ),
            id="eofcreate_1_orphan_subcontainer_0",
        ),
        pytest.param(
            Container(
                sections=[
                    Section.Code(Op.PUSH1[0] + Op.RJUMP[0] + Op.STOP),
                    abort_sub_container,
                    Section.Container(Container.Code(Op.PUSH0 + Op.PUSH0 + Op.RETURN)),
                ],
                expected_bytecode="""
                ef000101000402000100060300020000001400000016ff000000008000016000e0000000ef000101000402000100
                01ff00000000800000feef00010100040200010003ff000000008000025f5ff3""",
                # Originally this test was "valid" because it was created
                # before "orphan subcontainer" rule was introduced.
                validity_error=EOFException.ORPHAN_SUBCONTAINER,
            ),
            id="two_orphan_subcontainers",
        ),
        pytest.param(
            Container(
                sections=[
                    Section.Code(
                        Op.CALLDATASIZE
                        + Op.PUSH1[0]
                        + Op.PUSH1[255]
                        + Op.PUSH1[0]
                        + Op.EOFCREATE[255]
                        + Op.POP
                        + Op.STOP
                    )
                ]
                + 256 * [abort_sub_container],
                # Originally this test was "valid" because it was created
                # before "orphan subcontainer" rule was introduced.
                validity_error=EOFException.ORPHAN_SUBCONTAINER,
            ),
            id="eofcreate_255_max_orphan_subcontainers",
        ),
        pytest.param(
            Container(
                sections=[Section.Code(Op.PUSH1[0] + Op.RJUMP[0] + Op.STOP)]
                + 256 * [abort_sub_container],
                # Originally this test was "valid" because it was created
                # before "orphan subcontainer" rule was introduced.
                validity_error=EOFException.ORPHAN_SUBCONTAINER,
            ),
            id="max_orphan_subcontainers",
        ),
    ],
)
def test_migrated_eofcreate(eof_test: EOFTestFiller, container: Container):
    """Tests migrated from EOFTests/efValidation/EOF1_eofcreate_valid_.json."""
    eof_test(container=container, expect_exception=container.validity_error)


def test_dangling_initcode_subcontainer_bytes(
    eof_test: EOFTestFiller,
):
    """Initcode mode EOF Subcontainer test with subcontainer containing dangling bytes."""
    eof_test(
        container=Container(
            sections=[
                returncode_code_section,
                Section.Container(
                    container=Container(
                        raw_bytes=stop_sub_container.data + b"\x99",
                    ),
                ),
            ],
            kind=ContainerKind.INITCODE,
        ),
        expect_exception=EOFException.INVALID_SECTION_BODIES_SIZE,
    )


def test_dangling_runtime_subcontainer_bytes(
    eof_test: EOFTestFiller,
):
    """Runtime mode EOF Subcontainer test with subcontainer containing dangling bytes."""
    eof_test(
        container=Container(
            sections=[
                eofcreate_code_section,
                Section.Container(
                    container=Container(
                        raw_bytes=returncode_sub_container.data + b"\x99",
                    ),
                ),
            ],
        ),
        expect_exception=EOFException.INVALID_SECTION_BODIES_SIZE,
    )
