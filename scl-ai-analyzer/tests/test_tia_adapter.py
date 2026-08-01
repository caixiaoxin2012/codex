from pathlib import Path

from scl_ai_analyzer.tia_adapter import TIAExportAdapter, render_tia_markdown


TIA_XML = '''
<Document>
  <SW.Blocks.FB>
    <AttributeList>
      <Attribute Name="Name">MotorControl</Attribute>
      <Attribute Name="Number">12</Attribute>
      <Attribute Name="ProgrammingLanguage">SCL</Attribute>
    </AttributeList>
    <ObjectList>
      <StructuredText>
FUNCTION_BLOCK "MotorControl"
VAR_INPUT
    Start : Bool;
END_VAR
BEGIN
END_FUNCTION_BLOCK
      </StructuredText>
    </ObjectList>
  </SW.Blocks.FB>
  <SW.Blocks.OB>
    <AttributeList>
      <Attribute Name="Name">MainCycle</Attribute>
      <Attribute Name="Number">1</Attribute>
      <Attribute Name="ProgrammingLanguage">LAD</Attribute>
    </AttributeList>
  </SW.Blocks.OB>
  <SW.Types.PlcStruct>
    <AttributeList>
      <Attribute Name="Name">UDT_Motor</Attribute>
    </AttributeList>
  </SW.Types.PlcStruct>
</Document>
'''


def test_parse_tia_xml_metadata_and_scl(tmp_path: Path) -> None:
    xml_path = tmp_path / "tia_export.xml"
    xml_path.write_text(TIA_XML, encoding="utf-8")

    result = TIAExportAdapter().scan(xml_path)

    assert [item.name for item in result.items] == [
        "MotorControl",
        "MainCycle",
        "UDT_Motor",
    ]
    assert result.items[0].item_type == "FUNCTION_BLOCK"
    assert result.items[0].number == "12"
    assert result.items[0].programming_language == "SCL"
    assert result.items[1].source_text is None
    assert result.items[2].item_type == "TYPE"
    assert len(result.scl_project.blocks) == 1
    assert result.scl_project.blocks[0].name == "MotorControl"


def test_tia_report_contains_object_index(tmp_path: Path) -> None:
    xml_path = tmp_path / "tia_export.xml"
    xml_path.write_text(TIA_XML, encoding="utf-8")

    report = render_tia_markdown(TIAExportAdapter().scan(xml_path))

    assert "TIA Portal 导出分析报告" in report
    assert "MotorControl" in report
    assert "MainCycle" in report
    assert "UDT_Motor" in report
    assert "可进入 SCL 解析器的程序块" in report
