from pathlib import Path

from scl_ai_analyzer.secure_tia_adapter import TIAExportAdapter
from scl_ai_analyzer.secure_xml import SecurePLCXMLLoader, XMLSecurityPolicy


def test_secure_tia_adapter_extracts_block(tmp_path: Path) -> None:
    path = tmp_path / "tia.xml"
    path.write_text(
        '''
<Document>
  <SW.Blocks.FB>
    <AttributeList>
      <Attribute Name="Name">FB_Test</Attribute>
      <Attribute Name="ProgrammingLanguage">SCL</Attribute>
    </AttributeList>
    <StructuredText>FUNCTION_BLOCK FB_Test
VAR_INPUT
    Start : Bool; // start command
END_VAR
BEGIN
END_FUNCTION_BLOCK</StructuredText>
  </SW.Blocks.FB>
</Document>
'''.strip(),
        encoding="utf-8",
    )

    result = TIAExportAdapter().scan(path)

    assert len(result.items) == 1
    assert result.items[0].name == "FB_Test"
    assert result.items[0].item_type == "FUNCTION_BLOCK"
    assert len(result.scl_project.blocks) == 1
    assert result.scl_project.blocks[0].name == "FB_Test"


def test_secure_tia_adapter_turns_size_rejection_into_warning(tmp_path: Path) -> None:
    path = tmp_path / "too_large.xml"
    path.write_text("<Document><Name>Demo</Name></Document>", encoding="utf-8")
    loader = SecurePLCXMLLoader(XMLSecurityPolicy(max_size_bytes=8))

    result = TIAExportAdapter(xml_loader=loader).scan(path)

    assert result.items == ()
    assert any("过大" in warning for warning in result.warnings)
