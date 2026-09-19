import pixeltable as pxt
import pixeltable.functions as pxtf
from pixeltable.functions.openai import chat_completions
from pixeltable.functions.document import document_splitter
from pixeltable.serving import FastAPIRouter

TableModel = pxt.model_base()


class Documents(TableModel, name='documents'):
    """Store documents."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    title: pxt.String
    document: pxt.Document
    author: pxt.String | None
    doc_type: pxt.String | None


class DocumentChunks(TableModel, name='document_chunks', base=Documents,
                     iterator=document_splitter(Documents.document, separators='paragraph')):
    """View: one row per paragraph chunk. `text` comes from the iterator."""

    chunk_summary = chat_completions(
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('Summarize this text in one sentence: {}', text)
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content

    key_points = chat_completions(
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('Extract the key point from this text, or say "none": {}', text)
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content


class Reports(TableModel, name='reports'):
    """Store business reports."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    report_name: pxt.String
    report_document: pxt.Document
    department: pxt.String
    report_date: pxt.String


class ReportSections(TableModel, name='report_sections', base=Reports,
                     iterator=document_splitter(Reports.report_document, separators='paragraph')):
    """View: one row per paragraph of a report."""

    section_summary = chat_completions(
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('Summarize this report paragraph in one sentence: {}', text)
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content

    metrics = chat_completions(
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('Extract any numerical metrics or KPIs from this paragraph. Format "Metric: Value" or "none": {}', text)
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content


class Contracts(TableModel, name='contracts'):
    """Store legal contracts."""
    id = pxt.Column(value=pxtf.uuid.uuid7(), primary_key=True)
    contract_name: pxt.String
    contract_document: pxt.Document
    parties: pxt.String
    contract_type: pxt.String


class ContractClauses(TableModel, name='contract_clauses', base=Contracts,
                      iterator=document_splitter(Contracts.contract_document, separators='paragraph')):
    """View: one row per paragraph of a contract."""

    clause_analysis = chat_completions(
        messages=[{
            'role': 'user',
            'content': pxtf.string.format('Describe the obligation or risk in this contract paragraph in one sentence: {}', text)
        }],
        model='gpt-4o-mini'
    ).choices[0].message.content


doc_router = FastAPIRouter(name='documents')
doc_router.add_insert_route(
    Documents,
    path='/documents',
    inputs=[Documents.title, Documents.document, Documents.author],
    outputs=[Documents.id]
)

report_router = FastAPIRouter(name='reports')
report_router.add_insert_route(
    Reports,
    path='/reports',
    inputs=[Reports.report_name, Reports.report_document, Reports.department, Reports.report_date],
    outputs=[Reports.id]
)

contract_router = FastAPIRouter(name='contracts')
contract_router.add_insert_route(
    Contracts,
    path='/contracts',
    inputs=[Contracts.contract_name, Contracts.contract_document, Contracts.parties, Contracts.contract_type],
    outputs=[Contracts.id]
)
