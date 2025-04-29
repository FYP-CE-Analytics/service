# crewai_service.py
import os
from typing import Type, Any, Optional, Dict, List
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from app.schemas.vector_store import VectorSearchResponse
from app.schemas.crewai_faq_service_schema import CrewAIFAQInputSchema
from app.services.pinecone_vector_store import PineconeVectorStore


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

    def __init__(self,  index_name: str, collection_name: str, threshold=0.1, **kwargs):
        super().__init__(**kwargs)
        try:
            self.vectorstore: PineconeVectorStore = PineconeVectorStore(
                index_name=index_name,
                namespace=collection_name,
                api_key=os.getenv("PINECONE_API_KEY"),
                **kwargs
            )
            self.collection_name = collection_name
            self.threshold = threshold
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
                query_string=query_string, collection_name=self.collection_name, top_k=3)
            return results
        except Exception as e:
            print(f"Error during vector search: {e}")
            return [{"error": f"Vector search failed: {e}"}]


class UnitAnalysisCrewService:
    def __init__(self,  index_name: str):
        self.llm = LLM(
            model="gemini/gemini-1.5-flash", api_key=os.getenv("GEMINI_API_KEY"))
        self.index_name = index_name
        self.rag_tool = None  # Will be initialized per-unit in setup_crew

    def _initialize_tools(self, collection_name: str):
        """Initializes tools that depend on the unit (collection_name)."""
        self.rag_tool = QuestionVectorSearchTool(
            index_name=self.index_name,
            collection_name=collection_name,
        )
        # self.file_writer_tool = FileWriterTool()

    def setup_crew(self, unit_id: str) -> Crew:
        """Sets up the Crew for a specific unit."""
        self._initialize_tools(unit_id)

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
            role="You are the chief lecturer at a university for {unit_name}. Your goal is to help address common questions.",
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
        themeExtractorTask = Task(
            description=(
                "Analyze the list of top questions provided: {questions}. "
                "For each question, use the vector search tool with the question's content as the query to find the top 3 semantically similar questions from the forum knowledge base. "
                "Group related questions together based on similarity and content. "
                "Identify the common underlying theme or point of confusion for each group. "
                "Focus on themes relevant to the unit: {unit_name}."
            ),
            expected_output=(
                "A list of identified themes. Each theme should include: \n"
                "- A concise title for the theme (e.g., 'Confusion about Assignment 1 Submission Format').\n"
                "- A brief summary of the core issue or question the theme represents.\n"
                "- A list of the initial question IDs and the similar question IDs/content retrieved from the vector search that support this theme."
            ),
            agent=themeExtractorAgent,
            # context potentially needed if questions are passed differently
        )

        faqWritingTask = Task(
            description=(
                "Using the identified common themes from the previous step, generate a draft FAQ section. "
                "For each theme, formulate 1-3 clear and concise questions that students likely have. "
                "Reference the provided unit content {content} and assessment details {assessment} to ensure questions are relevant and specific. "
                "Use the vector search tool if needed to retrieve specific examples of student phrasing for context. "
                "Do NOT provide answers; focus only on crafting effective questions for the FAQ."
            ),
            expected_output=(
                "A list of FAQ questions formatted clearly (e.g., using bullet points). "
                "Each question should directly address one of the identified themes. "
                "Example: \n"
                "*   How do I correctly format my code submission for Assignment 1?\n"
                "*   What are the specific requirements for the methodology section in the final report?\n"
                "*   Where can I find examples of acceptable citations?"
            ),
            agent=faqWriterAgent,
            # Make sure this task depends on the output of the previous one
            context=[themeExtractorTask]
        )

        reportWritingTask = Task(
            description=(
                "Compile a summary report for the teaching team based on this week's analysis. Include the following sections:\n"
                "1.  **Overview:** Briefly state the period analyzed and the number of questions processed.\n"
                "2.  **Major Themes:** List the key themes identified by the Theme Extractor, perhaps noting their frequency or the number of related questions found.\n"
                "3.  **Assessment Links:** Briefly mention if/how the themes relate to specific assessments or unit content (using {assessment} and {content} context).\n"
                "4.  **Potential Blockers:** Highlight any significant misconceptions or difficulties indicated by the themes.\n"
                "5.  **Draft FAQ:** Include the generated FAQ questions from the FAQ Writer.\n"
                "Structure the report for clarity and easy digestion by educators. Use the file writer tool to save the report."
            ),
            expected_output=(
                "A well-structured weekly report document summarizing student question trends, analysis, and the generated FAQ draft, saved to a file."
            ),
            agent=reportWriterAgent,
            # Depends on both previous tasks
            context=[themeExtractorTask, faqWritingTask]
        )
        # Create and return the Crew
        crew = Crew(
            agents=[themeExtractorAgent, faqWriterAgent, reportWriterAgent],
            tasks=[themeExtractorTask, faqWritingTask, reportWritingTask],
            verbose=True,
            # process=Process.sequential,
            # llm=self.llm,
        )
        return crew

    def run(self, inputs: CrewAIFAQInputSchema) -> Any:
        """Runs the Crew with the given inputs."""
        unit_id = inputs.unit_id
        unit_name = inputs.unit_name
        if not unit_id or not unit_name:
            raise ValueError(
                "unit_id and unit_name must be provided in inputs")

        crew = self.setup_crew(unit_id)
        # Prepare inputs specifically for kickoff, ensuring keys match task expectations
        kickoff_inputs = {
            "unit_name": unit_name,
            "questions": inputs.questions,
            "content": inputs.content,
            "assessment": "",
        }
        print(f"Running crew with inputs: {kickoff_inputs}")
        result = crew.kickoff(inputs=kickoff_inputs)
        return result
