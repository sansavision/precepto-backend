import asyncio
import json
from typing import List
import unittest
# from agent_phi import SummarizationService
# from agent_phi_team3 import SummarizationService
# from agent_phi_team7 import SummarizationWorkflow
# from agent_py_team import SummarizationWorkflow
from agent_py_team4_x import SummarizationWorkflow
# from agein_lang_team import SummarizationService
from phi.model.openai import OpenAIChat
import openai
from phi.agent import Agent
class TestSummarizationService(unittest.TestCase):
    def setUp(self):
        self.llm_config = {
            "config_list": [{
                # "model": "gemma-9",
                # "model": "phi-4",
                # "model": "gemma2-9b-it",
                # "model": "gemma2:9b-instruct-q8_0",
                # "model": "bartowski/Marco-o1-exl2",
                # "model": "Marco-o1-exl2",
                # "model": "Phi4",
                "model": "Gemma",
                # "base_url": "http://localhost:8004/v1",
                # "base_url": "http://172.20.0.1:5000/v1/completions",
                "base_url": "http://localhost:5000/v1",
                # "base_url": "http://172.20.0.1:5000",
                # "base_url": "http://localhost:5000",
                # "base_url": "http://127.0.0.1:5000/",
                # "base_url": "http://localhost:11434/v1",
                "api_key": "e9cde95b10b268f36a93fe002aa97c39",
                "api_type": "openai",
                "temperature": 0,
                "top_p": 0.950,
                "max_tokens": 8192,
                # "repeat_penalty":1.0
            }]
        }
        # self.service = SummarizationService(self.llm_config)
        # self.workflow = SummarizationWorkflow(llm_config=self.llm_config, session_id="summarization-workflow")
        # self.workflow = SummarizationWorkflow(llm_config=self.llm_config)

        self.workflow = SummarizationWorkflow(llm_config= self.llm_config)

        # self.service = SummarizationService(self.llm_config["config_list"][0])
    def create_openai_model(self) -> OpenAIChat:
        # Adapt this as needed based on how your llm_config is structured
        config = self.llm_config["config_list"][0]
        return OpenAIChat(
            model_name=config.get("model", "gpt-4"),
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url", ""),
            temperature=config.get("temperature", ""),
            max_completion_tokens=config.get("max_tokens", 4096),
        )
    def create_openai_model2(self) -> openai.Client:
        # Adapt this as needed based on how your llm_config is structured
        config = self.llm_config["config_list"][0]
        return openai.Client(
            # model_name=config.get("model", "gpt-4"),
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url", ""),
            # temperature=config.get("temperature", ""),
            # max_completion_tokens=config.get("max_tokens", 4096),
        )
    async def test_generate_summary(self):
        self.setUp()
        t_long = """
0.00-5.00:   Jeg har hatt smerter i brystet de siste dagene, særlig når jeg går opp trapper eller gjør noe fysisk anstrengende. 
5.00-11.40:  Kan jeg beskrive smertene? De føles trykkende, og noen ganger stråler de mot venstre skulder og opp i nakken.
11.40-16.70:  Det oppstår ofte sammen med kortpustethet og svette. Jeg kjenner også at jeg blir litt svimmel.
16.70-23.35:  Jeg har røykt noen sigaretter om dagen i flere år, og faren min hadde hjerteinfarkt da han var 57. Jeg vet at jeg har høyt blodtrykk.
23.35-28.25:  Før vi går videre, vil jeg gjøre en grundig undersøkelse av deg: Vi skal måle blodtrykket, sjekke oksygenmetningen og lytte på hjertet og lungene.
28.25-35.00:  Blodtrykket blir målt, og det er 150/95. Pulsoximeteret viser en oksygenmetning på 97 % ved romluft.
35.00-40.50:  Jeg lytter nå på hjertet ditt. Hjertelydene er regelmessige, S1 og S2 høres tydelig og det er ingen bilyder (murmurs).
40.50-45.75:  Jeg lytter på lungene dine med stetoskopet. Pusten er ren bilateralt, uten ralinger, pipelyder eller andre unormale lyder.
45.75-52.60:  Pulsen din er jevn og ligger rundt 82 slag i minuttet. Du virker litt anspent, men ingen akutte funn utenom det forhøyede blodtrykket.
52.60-59.80:  Jeg ønsker også å ta et EKG for å se etter tegn til iskemi. La meg koble deg opp, dette tar bare et lite øyeblikk.
59.80-66.10:  EKG-resultatene viser enkelte ST-depresjoner i laterale avledninger, noe som kan indikere mulig angina pectoris.
66.10-71.70:  Jeg vil i tillegg ta noen blodprøver, inkludert troponin, for å se om det er tegn til hjertemuskelbelastning.
71.70-78.00:  Siden du har flere risikofaktorer – blant annet røykingen, familiehistorie med hjerteinfarkt og høyt blodtrykk – bør vi være ekstra forsiktige.
78.00-84.75:  Jeg vil starte deg på en betablokker for å avlaste hjertet, samt foreskrive nitroglyserin ved behov om smertene kommer tilbake.
84.75-91.20:  Vi bør også snakke om livsstil. Det er viktig at du forsøker å slutte å røyke og reduserer saltinntaket. Litt forsiktig mosjon kan også hjelpe.
91.20-96.90:  Siden EKG-et viser mulig iskemi, anbefaler jeg at vi legger deg inn på sykehuset for videre vurdering. De kan ta flere prøver og gjøre et arbeids-EKG.
96.90-104.40:  På sykehuset kan de også gjøre en ultralyd av hjertet for å se hvordan hjertemuskelen pumper, og eventuelt en koronar angiografi hvis det er mistanke om tette årer.
104.40-109.25:  Jeg skriver en henvisning med funnene så langt. Ambulansen kommer for å hente deg snart, så får du en grundig utredning.
109.25-115.80:  Husk å si ifra dersom smertene skulle forverre seg, eller hvis du opplever tung pust eller svimmelhet før du blir hentet.
115.80-120.95:  Det kan være skremmende, men det er viktig å få undersøkt dette nøye for å forebygge alvorlige komplikasjoner.
120.95-128.00:  Lykke til, jeg følger opp i etterkant når du er utskrevet fra sykehuset, og vi kan sette opp en plan for videre behandling.
"""
        transcript = """
        8.84-15.76:  Jeg har hatt vondt i brystet de siste par dagene, spesielt når jeg går opp trapper.
        15.76-29.95:  Forstår. Kan du beskrive smerten nærmere? Er den skarp, trykkende eller brennende? Det føles mest trykkende, som om noe tynger brystet mitt.
        30.27-36.35:  Har du merket andre symptomer, som svimmelhet, svette eller kortpustethet?
        36.35-39.75:  Ja, jeg har også fulgt med litt svimmel,
        39.83-43.51:  og har svettet mye uten å gjøre noen fysikk.
        43.51-50.85:  Har du noen tidligere helseproblemer, f.eks. høyt blodtrykk eller hjerteproblemer i familien?
        50.97-59.25:  Jeg har høyt blodtrykk, og min far hadde et hjerteinfarkt da han var 55 år gammel.
        59.25-82.67:  Jeg forstår. Basert på symptomene dine og din medisinske historie mistenker jeg at det kan være angina pectoris.
        60.25-82.67:  Blodtrykket ditt er 142/90, og EKG-resultatene viser tegn til iskemi.
        82.67-86.85:  Vi bør starte med GD-medisiner som kan hjelpe deg.
        86.85-92.03:  Og jeg anbefaler også noen livsstilsendringer.
        92.03-95.49:  Hva slags medisiner og endringer?
        95.57-100.13:  Jeg vil starte deg på betablokka for å redusere hjertets arbeidsbelastning.
        100.21-106.69:  Det er viktig å redusere saltinntaket og øke fysisk aktivitet gradvis.
        106.77-114.21:  Vi bør også sette opp en oppfølgingsavtale. Om en uke skal vi se hvordan du har det.
        114.21-118.34:  Takk, det høres fornuftig ut. Jeg skal prøve å følge rådene dine.
        118.42-125.46:  Hvis smertene blir verre eller du opplever nye symptomer, kontakt legen umiddelbart.
        125.58-129.22:  Vi tar godt vare på deg. Takk for hjelpen.
        """
        
        template = {
            "title": "Clinical Note",
            "content": [
                {
                    "section": "Anamnese",
                    "isMandatory": True,
                    "content": [
                        {
                            "timestamp": "???",
                            "description": "???"
                        }
                    ]
                },
                {
                    "section": "Funn",
                    "isMandatory": True,
                    "content": [
                        {
                            "timestamp": "???",
                            "description": "???"
                        }
                    ]
                },
                {
                    "section": "Andre us",
                    "isMandatory": True,
                    "content": [
                        {
                            "timestamp": "???",
                            "description": "???"
                        }
                    ]
                },
                {
                    "section": "Lab",
                    "isMandatory": True,
                    "content": [
                        {
                            "timestamp": "???",
                            "description": "???"
                        }
                    ]
                },
                {
                    "section": "Vurdering",
                    "isMandatory": True,
                    "content": [
                        {
                            "timestamp": "???",
                            "description": "???"
                        }
                    ]
                },
                {
                    "section": "Tiltak",
                    "isMandatory": True,
                    "content": [
                        {
                            "timestamp": "???",
                            "description": "???"
                        }
                    ]
                },
                {
                    "section": "Medikasjon",
                    "isMandatory": True,
                    "content": [
                        {
                            "timestamp": "???",
                            "description": "???"
                        }
                    ]
                },
                {
                    "section": "Diagnose",
                    "isMandatory": True,
                    "content": [
                        {
                            "timestamp": "???",
                            "description": "???"
                        }
                    ]
                }
            ]
        }

        print("Transcript:", transcript)
        print("\nTemplate:", json.dumps(template, indent=2, ensure_ascii=False))
        

        # client = OpenAI(base_url="http://<host>:<port>/v1", api_key="sk-xxx")
    #     c1 = self.create_openai_model()
    #     c = self.create_openai_model2()
    #     print("Client:", c)
    #     print("Client dict:", c.__dict__)
    #     web_agent = Agent(
    #     model=c,
    #     # tools=[DuckDuckGo()],
    #     instructions=["Always include sources"],
    #     show_tool_calls=True,
    #     markdown=True,
    # )
    #     a = web_agent.run("Tell me about OpenAI Sora?", asynch=False)
    #     print("Agent:", a)
        # response = c.chat.completions.create(
        #     # model="gpt-4-vision-preview",
        #     model=self.llm_config["config_list"][0]["model"],
        #     messages=[
        #         {
        #             "role": "user",
        #             "content": [
        #                 {"type": "text", "text": "Tell me about OpenAI Sora?"},
        #             ],
        #         }
        #     ],
        # )
        
        # responses = list(await self.workflow.run(transcript, template))
        # responses = list(self.workflow.run(transcript, template))
        # async for result in self.workflow.run(transcript, template):
        async for result in self.workflow.run(t_long, template):
            print("\nGenerated summary:")
            print("Responses:",result)
        # responses = await self.service.generate_summary(transcript, template)
        # print("Responses:", responses)
        # if responses:
        #     print(json.dumps(responses.model_dump(), indent=2))
        # else:
        #     print("Failed to generate summary")
        #     print("Responses:", responses)
        # Print the final response
        # for r in responses:
        #     print("Response object : \n")
        #     print( r)
        #     print("Response content : \n")
        #     print(r.content)
        # summary = self.service.generate_summary(transcript, template)
        # print("Summary:", summary)
        # summary = "response"
        # summary = None
        # print("\nGenerated summary:")
        # if summary:
        #     print(json.dumps(summary.model_dump(), indent=2, ensure_ascii=False))
        # else:
        #     print("No summary generated")

        # self.assertIsNotNone(summary, "Summary should not be None")
        # if not summary.section:
        #     return summary
        # # Additional validations
        # if summary:
        #     # Verify no template examples are used
        #     template_examples = self.extract_template_examples(template)
        #     summary_text = json.dumps(summary.model_dump())
        #     for example in template_examples:
        #         self.assertNotIn(example, summary_text, f"Template example '{example}' found in generated summary")
            
        #     # Verify mandatory sections are present
        #     mandatory_sections = {section['section'] for section in template['content'] if section['isMandatory']}
        #     summary_sections = {section.section for section in summary.content}
        #     for section in mandatory_sections:
        #         self.assertIn(section, summary_sections, f"Mandatory section '{section}' missing from summary")

    def extract_template_examples(self, template: dict) -> List[str]:
        """Extract example content from template for validation."""
        examples = []
        for section in template['content']:
            for entry in section['content']:
                if isinstance(entry, dict):
                    if 'description' in entry:
                        examples.append(entry['description'])
                    else:
                        examples.extend(entry.values())
        return [ex for ex in examples if ex != "???"]

if __name__ == '__main__':
    service = TestSummarizationService()
    # service.test_generate_summary()
    asyncio.run(service.test_generate_summary())
    # asyncio.run(service.test_generate_summary())
    # unittest.main(verbosity=2)

    # python -m llama_cpp.server --port 8004--n_gpu_layers -1  --n_ctx 16192 --model g*
    # python -m llama_cpp.server --port 8004 --n_gpu_layers 10  --n_ctx 8096 --model g*
    # python -m llama_cpp.server --port 8004 --n_gpu_layers -1  --n_ctx 3096 --model mo*/g*/g*
    # python -m llama_cpp.server --config_file llm_server_config.json