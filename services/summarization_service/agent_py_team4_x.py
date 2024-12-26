from typing import Dict, Any, AsyncIterator, Optional, List
from dataclasses import dataclass
from pydantic import BaseModel, Field, ValidationError
from pydantic_ai import Agent, RunContext, ModelRetry, UnexpectedModelBehavior
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIModel
import json
import ast
import logging
from textwrap import dedent

logger = logging.getLogger(__name__)
import logfire

logfire.configure() 
class Entry(BaseModel):
    timestamp: str = Field(
        ...,
        description="Timestamp in format 'number-number' or '???' for missing information",
        examples=["12.34-15.67", "???"]
    )
    description: str = Field(
        ...,
        description="Medical observation, finding, or action taken during this time period",
        min_length=1
    )

class Section(BaseModel):
    section: str = Field(
        ...,
        description="Name of the clinical note section",
        examples=["Anamnese", "Funn", "Vurdering"]
    )
    content: List[Entry] = Field(
        ...,
        description="List of timestamped entries in this section",
        min_items=1
    )
    isMandatory: bool = Field(
        default=False,
        description="Whether this section must be present in the note"
    )

class Note(BaseModel):
    title: str = Field(
        default="Clinical Note",
        description="Title of the clinical note"
    )
    content: List[Section] = Field(
        ...,
        description="List of sections containing medical information",
        min_items=1
    )

@dataclass
class SummarizationDeps:
    template: Dict[str, Any]
    transcript: str

# agent: Agent[SummarizationDeps, Note] = Agent(
agent = Agent(
    # 'groq:gemma2-9b-it',
    'test',
    # result_type=Note,
    deps_type=SummarizationDeps,
    retries=1,
    result_retries=1,
    model_settings={"top_p": 0.95, "temperature":0.0},
    # end_strategy="exhaustive",
    defer_model_check=True,
)


# def parse_note_from_json(json_str: str) -> Optional[Note]:
#     try:
#         note = Note.model_validate_json(json_str)
#         return note
#     except ValidationError as e:
#         print(f"Error parsing note: {e}")
#         return None





def extract_json(response: str) -> dict:
    # Strip and remove triple backticks and language hint lines if present
    response = response.strip()
    if response.startswith("```"):
        # If the response starts with triple backticks, split by newlines
        lines = response.split("\n")
        # Remove the first and last line if they are triple backticks
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        response = "\n".join(lines).strip()

    # Now try to load it as JSON directly
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        # If that fails, it might be single-quoted. Try literal_eval.
        try:
            data = ast.literal_eval(response)
            # Now convert data (a Python dict) to proper JSON format
            return json.loads(json.dumps(data))
        except Exception as e:
            raise ValueError("Unable to parse the LLM output as JSON or Python dict") from e

@agent.result_validator
async def validate_result(ctx: RunContext[SummarizationDeps], result: Note) -> Note:
    print("Validating result \n")
    print(result)
 
    if isinstance(result, Note):
        print("Result is Note Success \n")
        return result
    try:
        # # Remove leading/trailing whitespace
        # response = result.strip()
        # # Check if the response starts with ```json and ends with ```
        # if response.startswith("```json") and response.endswith("```"):
        #     # Remove the first line and the last line
        #     lines = response.split("\n")
        #     # Typically the first line is ```json and the last line is ```
        #     # Join everything in between
        #     json_str = "\n".join(lines[1:-1])
        # else:
        #     # If formatting is different, adjust accordingly
        #     json_str = response
        # json.loads(json_str)
        data = extract_json(result) 
        # Convert the dict to a Note instance using Pydantic
        r = Note.model_validate(data)
        print("After parse result \n")
        print(r," \n")
        logger.info(f"Result after parse logger: {r}")
        if r is None:
            print(f"Unexpected model response After parse result: \n")
            raise ModelRetry(f"Please try again and make sure to follow the instructions. the output is not a Note")
        return r
    except Exception as e:
        print(f"Unexpected model response exception After parse result error----xxxxxx----xxxxxxx: \n")
        print(f"{e}")
        print(f"Unexpected model response exception After parse result: \n")
        print(f"{result}")
        raise ModelRetry(f"Please try again and make sure to follow the instructions. the output is not a Note, {e}")

class SummarizationWorkflow:
    def __init__(self, llm_config: Dict[str, Any]):
        base_config = llm_config["config_list"][0]
        
        client = AsyncOpenAI(
            api_key=base_config.get("api_key", ""),
            base_url=base_config.get("base_url", ""),
            _strict_response_validation=True
        )
 
        self.model = OpenAIModel(
            base_config.get("model", "gemma2-9b-it"),
            openai_client=client
        )   
        agent.model = self.model



    @staticmethod
    def anormalize_template(template: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize template structure and extract section information."""
        normalized = {
            "title": template.get("title", "Clinical Note"),
            "content": []
        }

        section_info = {}
        for section in template["content"]:
            section_name = section["section"]
            section_info[section_name] = {
                "isMandatory": section.get("isMandatory", False),
                "order": len(section_info)
            }
            
            normalized_section = {
                "section": section_name,
                "isMandatory": section.get("isMandatory", False),
                "content": []
            }
            normalized["content"].append(normalized_section)

        return normalized, section_info

    # @staticmethod
    def _normalize_template(self,template: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize template structure and validate required sections."""
        try:
            normalized = {
                "title": template.get("title", "Clinical Note"),
                "content": []
            }
            
            mandatory_sections = set()
            for section in template["content"]:
                if section.get("isMandatory"):
                    mandatory_sections.add(section["section"])
                
                normalized_section = {
                    "section": section["section"],
                    "isMandatory": section.get("isMandatory", False),
                    "content": []
                }
                
                for entry in section["content"]:
                    if isinstance(entry, dict):
                        if "timestamp" in entry and "description" in entry:
                            normalized_section["content"].append(entry)
                        else:
                            for timestamp, description in entry.items():
                                normalized_section["content"].append({
                                    "timestamp": timestamp,
                                    "description": description
                                })
                
                normalized["content"].append(normalized_section)
            
            # Validate all mandatory sections are present
            if missing_sections := mandatory_sections - {s["section"] for s in normalized["content"]}:
                raise ModelRetry(f"Missing mandatory sections: {', '.join(missing_sections)}")
                
            return normalized
            
        except Exception as e:
            raise ModelRetry(f"Template normalization failed: {str(e)}")
    async def _validate_note(self, note: Note, ctx: RunContext[SummarizationDeps], section_info: Dict[str, Dict]) -> None:
        """Validate note structure and content."""
        issues = []
        
        # Check sections
        found_sections = {section.section for section in note.content}
        required_sections = {name for name, info in section_info.items() 
                           if info["isMandatory"]}
        
        if missing := required_sections - found_sections:
            raise ModelRetry(f"Missing required sections: {', '.join(missing)}")
            
        # Check section names
        invalid_sections = found_sections - section_info.keys()
        if invalid_sections:
            raise ModelRetry(f"Invalid section names: {', '.join(invalid_sections)}")

        # Validate order and timestamps
        for section in note.content:
            # Check section order
            if section.section in section_info:
                section_order = section_info[section.section]["order"]
                
                # Validate timestamps
                for entry in section.content:
                    if entry.timestamp != "???":
                        try:
                            start, end = map(float, entry.timestamp.split("-"))
                            if start >= end:
                                issues.append(
                                    f"Invalid timestamp range in {section.section}: {entry.timestamp}"
                                )
                        except (ValueError, AttributeError):
                            issues.append(
                                f"Malformed timestamp in {section.section}: {entry.timestamp}"
                            )

        if issues:
            raise ModelRetry("\n".join(issues))


    @agent.system_prompt
    async def get_system_prompt(ctx: RunContext[SummarizationDeps]) -> str:
        r = dedent(f"""
            You are a medical transcription assistant that converts conversations into structured clinical notes.

            Rules:
            - Use exact section names from the template
            - Use only information from the transcript
            - Use professional medical terminology in Norwegian
            - Timestamps must be "number-number" or "???"
            - If content is marked as mandatory but there is no relevant information it must be "???"
            - All mandatory sections must have content
            - No informal dialogue or questions
            - JSON should have double quotes and no trailing commas
            - Output must be properly formatted JSON
            
            Template:
            {ctx.deps.template}        
                   """).strip()
        
        print("System prompt: \n")
        print(r)
        logger.info(f"System prompt: {r}")
        return r
    
            # Transcript:
            # {ctx.deps.transcript}       

            # Transcript:
            # {ctx.deps.transcript}   
        
    
    async def run(self, transcript: str, template: Dict[str, Any]) -> AsyncIterator[str]:
        """Generate a clinical note from the transcript using the template structure."""
        normalized_template = self._normalize_template(template)
        print("Normalized template: \n")
        print(normalized_template)
        deps = SummarizationDeps(template=normalized_template, transcript=transcript)
# Template structure with 

        #  f"These are the template sections:\n{json.dumps(normalized_template, indent=2)}\n\n"
        #         f"Convert this medical transcript to a structured clinical note:\n\n{transcript}",
        # a = self.get_system_prompt(normalized_template,transcript)
        try:
            print("Running agent \n")
            result = await agent.run(
                # f' "Convert the transcript to a structured clinical note" {a}',
                # f"These are the template sections:\n{json.dumps(normalized_template, indent=2)}\n\n"
                f"Convert this medical transcript to a structured clinical note:\n\n{transcript}",
                deps=deps,
            )
            print("Agent result: \n")
            print(result)
            if isinstance(result.data, Note):
                # return result.data.note.model_dump()
                yield result.data
                # try:
                #     await self._validate_note(result.data.note, result.context, section_info)
                #     yield json.dumps(result.data.note.model_dump(), indent=2)
                # except ModelRetry as e:
                #     yield f"Validation failed: {str(e)}"
            else:
                yield f"Failed to generate note: {result.data.error_message}"
                if result.data.issues:
                    yield "\nIssues found:"
                    for issue in result.data.issues:
                        yield f"- {issue}"

        except UnexpectedModelBehavior as e:
            logger.error(f"Model behavior error: {str(e)}")
            logger.error(f"Last messages: {agent.last_run_messages}")
            yield (
                "Model response format error. Expected Success or InvalidNote object. "
                "Found text response instead. Please try again."
            )
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            yield f"An unexpected error occurred: {str(e)}"