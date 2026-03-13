# Copyright Daniel Lee Barren 2026
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent

from crewai_tools import CodeInterpreterTool

from .security_guard import get_rate_limited_serper, get_rate_limited_website_search
from .tools.docs_tools import read_reference_docs, save_to_notes


@CrewBase
class GenericConsultantCrew:
    """Generic market research and consulting crew for any industry and client type."""

    agents: list[BaseAgent]
    tasks: list[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def project_manager(self) -> Agent:
        # Manager agent must not have tools (CrewAI hierarchical requirement).
        return Agent(
            config=self.agents_config["project_manager"],  # type: ignore[index]
            tools=[],
        )

    @agent
    def market_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["market_researcher"],  # type: ignore[index]
            tools=[
                get_rate_limited_serper(),
                get_rate_limited_website_search(),
                read_reference_docs,
            ],
        )

    @agent
    def competitor_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["competitor_analyst"],  # type: ignore[index]
            tools=[
                get_rate_limited_serper(),
                get_rate_limited_website_search(),
                read_reference_docs,
            ],
        )

    @agent
    def solution_architect(self) -> Agent:
        code_interpreter = CodeInterpreterTool(unsafe_mode=False)
        return Agent(
            config=self.agents_config["solution_architect"],  # type: ignore[index]
            tools=[read_reference_docs, save_to_notes, code_interpreter],
        )

    @agent
    def note_taker(self) -> Agent:
        return Agent(
            config=self.agents_config["note_taker"],  # type: ignore[index]
            tools=[save_to_notes],
        )

    @agent
    def business_model_pricing_strategist(self) -> Agent:
        return Agent(
            config=self.agents_config["business_model_pricing_strategist"],  # type: ignore[index]
            tools=[read_reference_docs, save_to_notes],
        )

    @agent
    def code_writer_technical_architect(self) -> Agent:
        code_interpreter = CodeInterpreterTool(unsafe_mode=False)
        return Agent(
            config=self.agents_config["code_writer_technical_architect"],  # type: ignore[index]
            tools=[read_reference_docs, save_to_notes, code_interpreter],
        )

    @agent
    def report_formatter_pdf_generator(self) -> Agent:
        return Agent(
            config=self.agents_config["report_formatter_pdf_generator"],  # type: ignore[index]
            tools=[read_reference_docs, save_to_notes],
        )

    @task
    def load_reference_docs(self) -> Task:
        return Task(
            config=self.tasks_config["load_reference_docs"],  # type: ignore[index]
            tools=[read_reference_docs],
            output_file="output/reference_docs_summary.md",
            markdown=True,
        )

    @task
    def market_research(self) -> Task:
        return Task(
            config=self.tasks_config["market_research"],  # type: ignore[index]
            context=[self.load_reference_docs()],
            output_file="output/market_research.md",
            markdown=True,
        )

    @task
    def competitor_analysis(self) -> Task:
        return Task(
            config=self.tasks_config["competitor_analysis"],  # type: ignore[index]
            context=[self.market_research()],
            output_file="output/competitor_analysis.md",
            markdown=True,
        )

    @task
    def approve_before_solution_design(self) -> Task:
        return Task(
            config=self.tasks_config["approve_before_solution_design"],  # type: ignore[index]
            context=[self.competitor_analysis()],
        )

    @task
    def solution_architecture_design(self) -> Task:
        return Task(
            config=self.tasks_config["solution_architecture_design"],  # type: ignore[index]
            context=[
                self.load_reference_docs(),
                self.competitor_analysis(),
                self.approve_before_solution_design(),
            ],
            output_file="output/solution_architecture.md",
            markdown=True,
        )

    @task
    def capture_consulting_notes(self) -> Task:
        return Task(
            config=self.tasks_config["capture_consulting_notes"],  # type: ignore[index]
            context=[
                self.load_reference_docs(),
                self.market_research(),
                self.competitor_analysis(),
                self.solution_architecture_design(),
            ],
        )

    @task
    def business_model_and_pricing(self) -> Task:
        return Task(
            config=self.tasks_config["business_model_and_pricing"],  # type: ignore[index]
            context=[
                self.market_research(),
                self.competitor_analysis(),
            ],
            output_file="output/business_model_pricing.md",
            markdown=True,
        )

    @task
    def code_writer_technical_implementation(self) -> Task:
        return Task(
            config=self.tasks_config["code_writer_technical_implementation"],  # type: ignore[index]
            context=[
                self.solution_architecture_design(),
                self.business_model_and_pricing(),
            ],
        )

    @task
    def approve_before_final_package(self) -> Task:
        return Task(
            config=self.tasks_config["approve_before_final_package"],  # type: ignore[index]
            context=[self.capture_consulting_notes()],
        )

    @task
    def compile_client_package(self) -> Task:
        return Task(
            config=self.tasks_config["compile_client_package"],  # type: ignore[index]
            context=[
                self.approve_before_final_package(),
                self.market_research(),
                self.competitor_analysis(),
                self.solution_architecture_design(),
                self.capture_consulting_notes(),
                self.business_model_and_pricing(),
            ],
            output_file="output/client_package.md",
            markdown=True,
        )

    @task
    def generate_html_report(self) -> Task:
        return Task(
            config=self.tasks_config["generate_html_report"],  # type: ignore[index]
            context=[
                self.load_reference_docs(),
                self.market_research(),
                self.competitor_analysis(),
                self.solution_architecture_design(),
                self.business_model_and_pricing(),
                self.capture_consulting_notes(),
                self.compile_client_package(),
            ],
            output_file="output/client_report.html",
            markdown=False,
        )

    @task
    def human_review(self) -> Task:
        return Task(
            config=self.tasks_config["human_review"],  # type: ignore[index]
            context=[self.generate_html_report()],
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Generic Consultant Crew for market research and solution design."""
        # Manager must not be in agents list (CrewAI validation). First agent is project_manager.
        worker_agents = self.agents[1:] if len(self.agents) > 1 else []
        return Crew(
            agents=worker_agents,
            tasks=self.tasks,
            process=Process.hierarchical,
            verbose=True,
            planning=True,
            planning_llm="openai/gpt-4o-mini",
            manager_agent=self.project_manager(),
            memory=False,  # Avoid "invalid model ID" embedding errors in headless/web UI runs
        )

