# crewai_service.py
import os
from typing import Type, Any, Optional, Dict, List
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from app.schemas.vector_store import VectorSearchResponse
from app.schemas.crewai_faq_service_schema import CrewAIFAQInputSchema, CrewAIFAQOutputSchema, CrewAIThemeOutputSchema, CrewAIFAQRunOutputSchema, CrewAIUnitTrendAnalysisInputSchema, CrewAIUnitTrendAnalysisOutputSchema, CrewAIAnalysisRunOutputSchema
from app.services.pinecone_vector_store import PineconeVectorStore
from app.utils.shared import parse_date


class QuestionVectorSearchToolInput(BaseModel):
    """Input schema for the QuestionVectorSearchTool."""
    query: dict = Field(
        "", description="The search query to find relevant forum posts follwing the format: {'description': 'content'}")


class QuestionVectorSearchTool(BaseTool):
    name: str = "question_vector_search_tool"
    description: str = (
        "Searches the student forum post knowledge base. Use this to find submissions based on content similarity using a 'query'."
        "The input should be a dictionary with the key 'description' containing the content to search for. "
        "The output will be a list of similar questions from the forum knowledge base."
    )
    args_schema: Type[BaseModel] = QuestionVectorSearchToolInput
    vectorstore: Any = None
    collection_name: str = ""
    threshold: float = 0.1
    filter: dict = None

    def __init__(self,  index_name: str, collection_name: str, threshold=0.1, filter:dict=None, **kwargs):
        super().__init__(**kwargs)
        try:
            api_key = os.getenv("PINECONE_API_KEY")
            if not api_key:
                raise ValueError(
                    "Pinecone API key is not set in environment variables.")
            self.vectorstore: PineconeVectorStore = PineconeVectorStore(
                index_name=index_name,
                namespace=collection_name,
                api_key=api_key,
                **kwargs
            )
            self.collection_name = collection_name
            self.threshold = threshold
            self.filter = filter
            print(
                f"Vector store initialized for collection: {collection_name}")
        except Exception as e:
            print(f"Error initializing vector store: {e}")
            self.vectorstore = None  # Handle initialization failure gracefully

    def _run(self, query: dict = None, **kwargs) -> List[Dict[str, Any]]:
        if self.vectorstore is None:
            return [{"error": "Vector store not initialized."}]
        if not query:
            return [{"error": "Tool requires query to search for similar questions."}]
        query_string = query.get("description", "")

        try:
            results = self.vectorstore.search_with_string(
                query_string=query_string, collection_name=self.collection_name, filter=self.filter)
            if not results:
                return [{"result": "No related questions found."}]
            # if results:
            #     # parse the date
            #     start_date = self.start_date
            #     end_date = self.end_date
            #     # filer out the results to select only the result wihin the start and end date
            #     results = [result for result in results if parse_date(
            #         result["created_at"]) >= start_date and parse_date(result["created_at"]) <= end_date]
            if len(results) == 0:
                return [{"result": "No related questions found."}]
            return results
        except Exception as e:
            print(f"Error during vector search: {e}")
            return [{"error": f"Vector search failed: {e}"}]


class UnitFAQCrewService:
    def __init__(self,  index_name: str):
        self.llm = LLM(
            model="gemini/gemini-2.0-flash", api_key=os.getenv("GEMINI_API_KEY"))
        self.index_name = index_name
        self.rag_tool = None  # Will be initialized per-unit in setup_crew
        self.theme_extractor_task = None
        self.faq_writer_task = None
        self.report_writer_task = None

    def _initialize_tools(self, collection_name: str, week_number: int, **kwargs) -> None:
        """Initializes tools that depend on the unit (collection_name)."""
        print(f"Initializing tools for collection: {collection_name}")
        self.rag_tool = QuestionVectorSearchTool(
            index_name=self.index_name,
            collection_name=collection_name,
            week_number=week_number,
            filter={"week_id": {
                "$eq": week_number
            }},
            **kwargs
        )
        # self.file_writer_tool = FileWriterTool()

    def setup_crew(self, unit_id: str, week_number: int) -> Crew:
        """Sets up the Crew for a specific unit."""
        self._initialize_tools(collection_name=unit_id,
                               week_number=week_number)

        # Define Agents
        themeExtractorAgent = Agent(
            role="You are a high education university tutor for {unit_name}. Your goal is to help identify common questions.",
            goal="Extract the common theme of the questions students asked on the forum. This will then be used to help resolve their issues, including creating an FAQ or making modifications to assessment specifications.",
            backstory="You are a university tutor skilled at identifying recurring themes in student questions. Your task is to pinpoint these themes and understand the underlying points of confusion that need addressing.",
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            tools=[self.rag_tool]
        )

        faqWriterAgent = Agent(
            role="You are the chief lecturer at a university for {unit_name} teaching about {content}. Your goal is to help address common questions.",
            goal="Generate a clear and concise FAQ draft based on the common themes identified in student questions. Focus on formulating the questions; answers will be handled separately by the teaching staff.",
            backstory="An expert technical writer specializing in educational content, adept at creating helpful FAQs for students based on identified needs.",
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            tools=[self.rag_tool]
        )

        reportWriterAgent = Agent(
            role="You are the chief lecturer at a university for {unit_name}. Your goal is to synthesize analysis findings for the teaching team.",
            goal="Synthesize all findings (themes, related questions, assessment links, FAQ draft) into a summary report. Highlight trends, potential blockers, and areas needing attention for unit improvement.",
            backstory="Dedicated to weekly unit improvement, you create insightful executive summaries for the teaching team, focusing on actionable insights derived from student question data.",
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            tools=[]
        )

        # Define Tasks
        self.theme_extractor_task = Task(
            description=(
                "Analyze the list of top questions provided: {questions} on the given week {week} "
                "For each question, use the vector search tool with the question's content as the query to find the top 3 semantically similar questions from the forum knowledge base. "
                "Group related questions together based on similarity and content. "
                "Identify the common underlying theme or point of confusion for each group. "
                "Focus on themes relevant to the unit: {unit_name} with the weekly contain {weekly_content}"
                "There could be other unrelated questions such as admin or technical issues, please provide a list of those questions separately. "
            ),
            expected_output=(
                "A list of identified themes. Each theme should include: \n"
                "- A concise title for the theme (e.g., 'Confusion about Assignment 1 Submission Format').\n"
                "- A brief summary of the core issue or question the theme represents.\n"
                "- A list of similar question IDs retrieved from the vector search that support this theme. E.g. theme: 'Confusion about Assignment 1 Submission Format' \n"
                "  - Question IDs: [123, 456]\n"
            ),
            agent=themeExtractorAgent,
            output_pydantic=CrewAIThemeOutputSchema,
            # context potentially needed if questions are passed differently
        )

        self.faq_writer_task = Task(
            description=(
                "Using the identified common themes from the previous step, generate a draft FAQ section. "
                "For each theme, formulate 1-3 clear and concise questions that students likely have. "
                "Reference the provided overall unit content {content}, and more detail weekly content where the questions are extracted from {weekly_content} assessment details {assessment} to ensure questions are relevant and specific. "
                "Use the vector search tool if needed to retrieve specific examples of student phrasing for context. "
                "Do NOT provide answers; focus only on crafting effective questions for the FAQ."
                "Structure the report for clarity and easy digestion by educators"
            ),
            expected_output=(
                "A list of FAQ questions formatted in strcutred md forma clearly (e.g., using bullet points) used for FAQ draft "
                "Each question should directly address one of the identified themes. "
                "Make sure the my heading like FAQ 1, FAQ 2, FAQ 3 are present in the report and clearly separated. Make sure the analysis is in new lines and not just one line."
                "Example: \n"
                "FAQ 1 (Theme 1): \n"
                "*   How do I correctly format my code submission for Assignment 1?\n"
                "FAQ 2 (Theme 2): \n"
                "*   What are the specific requirements for the methodology section in the final report?\n"
                "FAQ 3 (Theme 3): \n"
                "*   Where can I find examples of acceptable citations?"
            ),
            agent=faqWriterAgent,
            # Make sure this task depends on the output of the previous one
            context=[self.theme_extractor_task],
            output_pydantic=CrewAIFAQOutputSchema
        )

        crew = Crew(
            agents=[themeExtractorAgent, faqWriterAgent, reportWriterAgent],
            tasks=[self.theme_extractor_task, self.faq_writer_task],
            verbose=True,
            # process=Process.sequential,
            # llm=self.llm,
        )
        return crew

    def run(self, inputs: CrewAIFAQInputSchema) -> CrewAIFAQRunOutputSchema:
        """Runs the Crew with the given inputs."""
        unit_id = inputs.unit_id
        unit_name = inputs.unit_name
        week_number = inputs.week
        if not unit_id or not unit_name:
            raise ValueError(
                "unit_id and unit_name must be provided in inputs")

        crew = self.setup_crew(
            unit_id, week_number=week_number)
        # Prepare inputs specifically for kickoff, ensuring keys match task expectations

        print(f"Running crew with inputs: {inputs.model_dump()}")
        result = crew.kickoff(inputs=inputs.model_dump()).pydantic
        print(result)

        print(self.theme_extractor_task.output.pydantic.model_dump())

        # Extract questions from theme extractor and report from FAQ writer
        theme_data = self.theme_extractor_task.output.pydantic
        faq_data = result

        return CrewAIFAQRunOutputSchema(
            report=faq_data.report,
            questions=theme_data.questions
        )


class UnitTrendAnalysisCrewService:
    def __init__(self,  index_name: str):
        self.llm = LLM(
            model="gemini/gemini-2.0-flash", api_key=os.getenv("GEMINI_API_KEY"))
        self.index_name = index_name
        self.rag_tool = None  # Will be initialized per-unit in setup_crew
        self.theme_extractor_task = None
        self.report_writer_task = None

    def _initialize_tools(self, collection_name: str, category:str) -> None:
        """Initializes tools that depend on the unit (collection_name)."""
        print(f"Initializing tools for collection: {collection_name}")
        self.rag_tool = QuestionVectorSearchTool(
            index_name=self.index_name,
            collection_name=collection_name,
            filter={"category": {
                "$eq": category
            }}

        )

    def setup_crew(self, unit_id: str, category:str) -> Crew:
        """Sets up the Crew for a specific unit."""
        self._initialize_tools(unit_id, category)

        # Define Agents
        themeExtractorAgent = Agent(
            role="You are a high education university tutor for {unit_name} teaching about {content}. Your goal is to help identify common questions.",
            goal="Extract the common theme of the questions students asked on the forum. This will then be used to help resolve their issues, including creating an FAQ or making modifications to assessment specifications.", 
            backstory="You are a university tutor skilled at identifying recurring themes and common misconceptions and struggles in student questions. Your task is to pinpoint these themes and understand the underlying points of confusion that need addressing. \
            Group the questions based on the similarity of the content and the theme of the question",
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            tools=[self.rag_tool]
        )

        reportWriterAgent = Agent(
            role="You are the chief lecturer at a university for {unit_name} teaching about {content}. Your goal is to synthesize analysis findings for the teaching team.",
            goal="Synthesize all findings into a summary report. Highlight common struggles, trends,potential common misconceptions and confusion among students, and areas needing attention for unit improvement. \
            provide evidence for the analysis and the findings by refering to the questions and maybe provide the question content",
            backstory="Dedicated to weekly unit improvement, you create insightful executive summaries for the teaching team, focusing on actionable insights derived from student question data",
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            tools=[self.rag_tool]
        )

        self.theme_extractor_task = Task(
            description=(
                "Analyze the list of top questions provided: {questions} on the given assessment category {category} "
                "For each question, use the vector search tool with the question's content as the query to find the top 3 semantically similar questions from the forum knowledge base. "
                "Group related questions together based on similarity and content. "
                "Identify the common underlying theme or point of confusion for each group. "
                "Group the questions based on the similarity of the content and the theme of the question"
            ),
            expected_output=(
                "A list of identified themes. Each theme should include: \n"
                "- A concise title for the theme (e.g., 'Confusion about Assignment 1 Submission Format').\n"
                "- A brief summary of the core issue or question the theme represents.\n"
                "- A list of the similar question IDs retrieved from the vector search that support this theme. E.g. theme: 'Confusion about Assignment 1 Submission Format' \
                  - Question IDs: [123, 456,789]"
            ),
            agent=themeExtractorAgent,
            output_pydantic=CrewAIThemeOutputSchema,
        )
        self.report_writer_task = Task(
            description=(
                "Compile a summary report for the teaching team based on the questions found on the assessment category {category}. Include the following sections:\n"
                "1.  **Overview:** Highlight the general trends discovered(are student more confused about the content, or more confused about the assessment format, or more confused about the submission format, etc.)\n"
                "2.  **Major Themes within the questions:** List the key themes identified by the Theme Extractor\n"
                "3.  **Potential Misconception and stuggles:** Highlight any significant misconceptions or difficulties student face on the {category} indicated by the themes.\n"
                "4.  **Recommendations:** Provide recommendations for the teaching team to address the potential blockers and improve the unit."

                "Structure the report for clarity and easy digestion by educators"
            ),
            expected_output=(
                "A well-structured report document summarizing student question trends, analysis, and the generated recommendations."
                "The report should be in well structured markdown format. for example: \n"
                "Make sure the my heading like overview, major themes, student common misconceptions, recommendations are present in the report and clearly separated. Make sure the analysis is in new lines and not just one line."
                "# Overview\n"
                "Analysis for {category} on {unit_name}\n"
                "## Major Themes\n"
                "- [theme1] - refer to the questions\n"
                "- [theme2] - refer to the questions\n"
                "# Student Common Misconceptions\n"
                "- [misconception1] - refer to the questions\n"
                "- [misconception2] - refer to the questions\n"
                "# Recommendations\n"
                "- [recommendation1]\n"
                "- [recommendation2]\n"
            ),
            agent=reportWriterAgent,
            # Depends on both previous tasks
            context=[self.theme_extractor_task],
            output_pydantic=CrewAIUnitTrendAnalysisOutputSchema,
        )
        # Create and return the Crew
        crew = Crew(
            agents=[themeExtractorAgent, reportWriterAgent],
            tasks=[self.theme_extractor_task, self.report_writer_task],
            verbose=True,
            # process=Process.sequential,
            # llm=self.llm,
        )
        return crew
    
    def run(self, inputs: CrewAIUnitTrendAnalysisInputSchema) -> CrewAIAnalysisRunOutputSchema:
        """Runs the Crew with the given inputs."""
        unit_id = inputs.unit_id
        unit_name = inputs.unit_name
        if not unit_id or not unit_name:
            raise ValueError(
                "unit_id and unit_name must be provided in inputs")

        crew = self.setup_crew(
            unit_id, category=inputs.category)
        # Prepare inputs specifically for kickoff, ensuring keys match task expectations

        print(f"Running crew with inputs: {inputs.model_dump()}")
        result = crew.kickoff(inputs=inputs.model_dump()).pydantic
        question_clusters = self.theme_extractor_task.output.pydantic

        print("question clusters: ", question_clusters)

        return CrewAIAnalysisRunOutputSchema(
            report=result.report,
            questions=question_clusters.questions
        )
