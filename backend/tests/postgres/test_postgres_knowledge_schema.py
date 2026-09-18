"""Actual PostgreSQL integrity, eligibility and guarded storage proofs."""

import asyncio
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models.knowledge import embedding_space_hash


pytestmark = pytest.mark.postgres
IDENTITY = ('openai_compatible', 'https://api.openai.com/v1', 'text-embedding-3-small',
            'v1', 'raw_text_v1', 1536, 'float32', 'cosine')
CONTENT = 'Synthetic teaching evidence.'


async def make_owner(connection):
    values = {'owner': uuid4(), 'subject': uuid4(), 'email': f'knowledge-{uuid4().hex}@example.test'}
    await connection.execute(text("INSERT INTO users(id,email,hashed_password,role) VALUES(:owner,:email,'fixture','INSTRUCTOR')"),values)
    await connection.execute(text("INSERT INTO subjects(id,name,instructor_id) VALUES(:subject,'Knowledge fixture',:owner)"),values)
    return values


async def make_space(connection, identity=IDENTITY):
    space_hash = embedding_space_hash(identity)
    values = dict(zip(('provider','base_url','model','space_revision','format_version','dimensions','representation','metric'),identity))
    values['space_hash'] = space_hash
    exists = await connection.scalar(text('SELECT 1 FROM rag_embedding_spaces WHERE identity_hash=:space_hash'),values)
    if not exists:
        await connection.execute(text('''INSERT INTO rag_embedding_spaces(identity_hash,provider,base_url,model,space_revision,format_version,dimensions,representation,metric)
            VALUES(:space_hash,:provider,:base_url,:model,:space_revision,:format_version,:dimensions,:representation,:metric)'''),values)
    return values


async def make_document(connection, values):
    values = {**values, 'document': uuid4()}
    await connection.execute(text('''INSERT INTO subject_documents(id,subject_id,uploader_id,title,source_pdf_name,source_sha256)
        VALUES(:document,:subject,:owner,'Fixture','fixture.pdf',repeat('a',64))'''),values)
    return values


async def make_ready(connection, owner_values):
    values = await make_document(connection, owner_values)
    values.update(await make_space(connection))
    values.update(content_revision=uuid4(),index_revision=uuid4(),chunk=uuid4(),content=CONTENT,
                  chars=len(CONTENT),bytes=len(CONTENT.encode()),charged=len(CONTENT.encode())+6408)
    await connection.execute(text('''INSERT INTO subject_document_content_revisions(id,document_id,subject_id,uploader_id,revision_no,
        source_sha256,extraction_version,reserved_page_count,reserved_page_chars,reserved_page_bytes)
        VALUES(:content_revision,:document,:subject,:owner,1,repeat('a',64),'canonical_v1',2,:chars,:bytes)'''),values)
    await connection.execute(text('''INSERT INTO subject_document_pages(content_revision_id,document_id,subject_id,uploader_id,page_number,content)
        VALUES(:content_revision,:document,:subject,:owner,1,:content),(:content_revision,:document,:subject,:owner,2,'')'''),values)
    await connection.execute(text("UPDATE subject_document_content_revisions SET status='pending_index' WHERE id=:content_revision"),values)
    await connection.execute(text('''INSERT INTO subject_document_index_revisions(id,content_revision_id,document_id,subject_id,uploader_id,
        revision_no,chunker_version,embedding_provider,embedding_base_url,embedding_model,embedding_space_revision,embedding_format_version,
        embedding_dimensions,embedding_representation,embedding_metric,embedding_space_hash,reserved_chunk_count,reserved_index_bytes)
        VALUES(:index_revision,:content_revision,:document,:subject,:owner,1,'bounded_v1',:provider,:base_url,:model,:space_revision,
        :format_version,:dimensions,:representation,:metric,:space_hash,1,:charged)'''),values)
    await connection.execute(text('''INSERT INTO subject_document_chunks(id,index_revision_id,content_revision_id,document_id,subject_id,uploader_id,
        chunk_index,page_number,content,token_count,embedding_space_hash,embedding)
        VALUES(:chunk,:index_revision,:content_revision,:document,:subject,:owner,0,1,:content,8,:space_hash,
        array_prepend(1::real,array_fill(0::real,ARRAY[1535]))::vector)'''),values)
    await connection.execute(text("UPDATE subject_document_index_revisions SET status='ready',is_active=true WHERE id=:index_revision"),values)
    await connection.execute(text("UPDATE subject_document_content_revisions SET status='ready',is_active=true WHERE id=:content_revision"),values)
    await connection.execute(text('UPDATE subjects SET active_embedding_space_hash=:space_hash WHERE id=:subject'),values)
    return values


@pytest_asyncio.fixture
async def knowledge_connection(postgres_engine):
    async with postgres_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            await transaction.rollback()


async def reject(connection, statement, values):
    with pytest.raises(DBAPIError) as failure:
        async with connection.begin_nested():
            await connection.execute(text(statement),values)
            # Composite provenance constraints deliberately defer until commit.
            await connection.execute(text('SET CONSTRAINTS ALL IMMEDIATE'))
    assert failure.value.orig.sqlstate in {'23503','23505','23514','22000','22023'}


async def test_ready_private_review_publication_active_revision_and_space_filter(knowledge_connection):
    connection=knowledge_connection
    values=await make_ready(connection,await make_owner(connection))
    eligible=text('SELECT count(*) FROM eligible_subject_knowledge_chunks WHERE subject_id=:subject')
    assert await connection.scalar(eligible,values)==0
    await reject(connection,"UPDATE subject_document_content_revisions SET published_at=now() WHERE id=:content_revision",values)
    await reject(connection,"UPDATE subject_document_content_revisions SET reviewed_at=now(),reviewed_by_id=:subject WHERE id=:content_revision",values)
    await connection.execute(text('UPDATE subject_document_content_revisions SET reviewed_at=now(),reviewed_by_id=:owner,published_at=now() WHERE id=:content_revision'),values)
    assert await connection.scalar(eligible,values)==1
    assert await connection.scalar(text("SELECT count(*) FROM eligible_subject_knowledge_chunks WHERE subject_id=:wrong"),{'wrong':uuid4()})==0
    different=await make_space(connection,(*IDENTITY[:3],'v2',*IDENTITY[4:]))
    await connection.execute(text('UPDATE subjects SET active_embedding_space_hash=:space_hash WHERE id=:subject'),{**values,'space_hash':different['space_hash']})
    assert await connection.scalar(eligible,values)==0
    await connection.execute(text('UPDATE subjects SET active_embedding_space_hash=:space_hash WHERE id=:subject'),values)
    await connection.execute(text('UPDATE subject_document_content_revisions SET published_at=NULL WHERE id=:content_revision'),values)
    assert await connection.scalar(eligible,values)==0
    await connection.execute(text('UPDATE subject_document_content_revisions SET published_at=now(),is_active=false WHERE id=:content_revision'),values)
    assert await connection.scalar(eligible,values)==0


async def test_measurements_vectors_provenance_and_immutable_identity(knowledge_connection):
    connection=knowledge_connection
    values=await make_ready(connection,await make_owner(connection))
    measured=(await connection.execute(text('''SELECT actual_page_count,actual_page_chars,actual_page_bytes
        FROM subject_document_content_revisions WHERE id=:content_revision'''),values)).one()
    assert measured==(2,len(CONTENT),len(CONTENT.encode()))
    assert await connection.scalar(text('SELECT actual_index_bytes FROM subject_document_index_revisions WHERE id=:index_revision'),values)==values['charged']
    from app.models.knowledge import SubjectDocumentChunk
    embedding=await connection.scalar(select(SubjectDocumentChunk.embedding).where(SubjectDocumentChunk.id==values['chunk']))
    assert len(embedding)==1536 and embedding[0]==1 and all(value==0 for value in embedding[1:])
    for statement in (
        "UPDATE subject_document_pages SET content='Changed' WHERE content_revision_id=:content_revision",
        'UPDATE subject_document_content_revisions SET actual_page_bytes=0 WHERE id=:content_revision',
        'UPDATE subject_document_index_revisions SET actual_index_bytes=0 WHERE id=:index_revision',
        "UPDATE subject_document_index_revisions SET embedding_model='other' WHERE id=:index_revision",
        'UPDATE knowledge_storage_usage SET charged_bytes=0 WHERE scope_id=:subject',
        'DELETE FROM knowledge_storage_usage WHERE scope_id=:subject',
        "UPDATE rag_embedding_spaces SET model='other' WHERE identity_hash=:space_hash",
        'UPDATE subject_document_chunks SET embedding=NULL WHERE id=:chunk',
        'UPDATE subjects SET corpus_revision=0 WHERE id=:subject',
        "UPDATE subject_document_content_revisions SET status='processing',is_active=false,reviewed_at=NULL,reviewed_by_id=NULL,published_at=NULL WHERE id=:content_revision",
        "UPDATE subject_document_index_revisions SET status='indexing',is_active=false WHERE id=:index_revision",
    ):
        await reject(connection,statement,values)
    await reject(connection,"UPDATE subject_document_content_revisions SET error_code='knowledge_index_failed',error_message='private details' WHERE id=:content_revision",values)
    await reject(connection,"UPDATE subject_document_content_revisions SET error_code='knowledge_index_failed',error_message=NULL WHERE id=:content_revision",values)
    await reject(connection,"INSERT INTO knowledge_storage_usage(scope_type,scope_id) VALUES('subject',:subject)",values)


async def test_document_deletion_detaches_job_set_preserves_cards_and_tombstone(knowledge_connection):
    connection=knowledge_connection
    values=await make_ready(connection,await make_owner(connection))
    values.update(job=uuid4(),set_id=uuid4(),card=uuid4())
    await connection.execute(text('''INSERT INTO generation_jobs(id,user_id,subject_id,document_id,idempotency_key_hash,request_fingerprint,
        status,set_title,requested_card_count,source_pdf_name) VALUES(:job,:owner,:subject,:document,repeat('b',64),repeat('c',64),
        'awaiting_upload','Fixture',5,'fixture.pdf')'''),values)
    await connection.execute(text('''INSERT INTO flashcard_sets(id,subject_id,title,generation_job_id,document_id)
        VALUES(:set_id,:subject,'Fixture',:job,:document)'''),values)
    await connection.execute(text('''INSERT INTO flashcards(id,set_id,front_content,back_content,options)
        VALUES(:card,:set_id,'Fixture question?','A','["A","B","C","D"]'::jsonb)'''),values)
    other=await make_owner(connection)
    await reject(connection,'UPDATE generation_jobs SET subject_id=:wrong WHERE id=:job',{**values,'wrong':other['subject']})
    await reject(connection,'UPDATE generation_jobs SET user_id=:wrong WHERE id=:job',{**values,'wrong':other['owner']})
    await reject(connection,'UPDATE flashcard_sets SET subject_id=:wrong WHERE id=:set_id',{**values,'wrong':other['subject']})
    await connection.execute(text('DELETE FROM subject_documents WHERE id=:document'),values)
    assert (await connection.execute(text('SELECT document_id,knowledge_capture_removed FROM generation_jobs WHERE id=:job'),values)).one()==(None,True)
    assert await connection.scalar(text('SELECT document_id FROM flashcard_sets WHERE id=:set_id'),values) is None
    assert await connection.scalar(text('SELECT count(*) FROM flashcards WHERE id=:card'),values)==1
    for table in ('subject_document_content_revisions','subject_document_pages','subject_document_chunks','subject_document_index_jobs'):
        assert await connection.scalar(text(f'SELECT count(*) FROM {table} WHERE document_id=:document'),values)==0
    await reject(connection,'UPDATE generation_jobs SET knowledge_capture_removed=false WHERE id=:job',values)


async def test_actual_rows_cannot_exceed_text_chunk_reservations_or_skip_original_page(knowledge_connection):
    connection=knowledge_connection
    values=await make_document(connection,await make_owner(connection))
    values.update(content_revision=uuid4(),index_revision=uuid4())
    values.update(await make_space(connection))
    await connection.execute(text('''INSERT INTO subject_document_content_revisions(id,document_id,subject_id,uploader_id,revision_no,
        source_sha256,extraction_version,reserved_page_count,reserved_page_chars,reserved_page_bytes)
        VALUES(:content_revision,:document,:subject,:owner,1,repeat('a',64),'v1',1,2,2)'''),values)
    await reject(connection,"INSERT INTO subject_document_pages(content_revision_id,document_id,subject_id,uploader_id,page_number,content) VALUES(:content_revision,:document,:subject,:owner,1,'éé')",values)
    await reject(connection,"INSERT INTO subject_document_pages(content_revision_id,document_id,subject_id,uploader_id,page_number,content) VALUES(:content_revision,:document,:subject,:owner,100,'ab')",values)
    await connection.execute(text("INSERT INTO subject_document_pages(content_revision_id,document_id,subject_id,uploader_id,page_number,content) VALUES(:content_revision,:document,:subject,:owner,1,'ab')"),values)
    await connection.execute(text("UPDATE subject_document_content_revisions SET status='pending_index' WHERE id=:content_revision"),values)
    await connection.execute(text('''INSERT INTO subject_document_index_revisions(id,content_revision_id,document_id,subject_id,uploader_id,revision_no,
        chunker_version,embedding_provider,embedding_base_url,embedding_model,embedding_space_revision,embedding_format_version,
        embedding_dimensions,embedding_representation,embedding_metric,embedding_space_hash,reserved_chunk_count,reserved_index_bytes)
        VALUES(:index_revision,:content_revision,:document,:subject,:owner,1,'v1',:provider,:base_url,:model,:space_revision,:format_version,
        :dimensions,:representation,:metric,:space_hash,1,6410)'''),values)
    insert='''INSERT INTO subject_document_chunks(index_revision_id,content_revision_id,document_id,subject_id,uploader_id,chunk_index,
        page_number,content,token_count,embedding_space_hash,embedding)
        VALUES(:index_revision,:content_revision,:document,:subject,:owner,0,:page,'ab',1,:space_hash,{vector})'''
    vector='array_prepend(1::real,array_fill(0::real,ARRAY[1535]))::vector'
    await reject(connection,insert.format(vector=vector),{**values,'page':2})
    await reject(connection,insert.format(vector=vector).replace(',0,:page',',511,:page'),{**values,'page':1})
    await reject(connection,insert.format(vector="array_fill(0::real,ARRAY[1536])::vector"),{**values,'page':1})
    await reject(connection,insert.format(vector="'[1,0]'::vector"),{**values,'page':1})
    await reject(connection,insert.format(vector="array_prepend('NaN'::real,array_fill(0::real,ARRAY[1535]))::vector"),{**values,'page':1})
    await reject(connection,insert.format(vector="array_prepend('Infinity'::real,array_fill(0::real,ARRAY[1535]))::vector"),{**values,'page':1})
    await reject(connection,insert.format(vector=vector),{**values,'page':1,'space_hash':'f'*64})
    from app.models.knowledge import SubjectDocumentChunk
    # Exercise the actual SQLAlchemy/asyncpg vector binding, not only SQL casts.
    await connection.execute(SubjectDocumentChunk.__table__.insert().values(
        index_revision_id=values['index_revision'],content_revision_id=values['content_revision'],
        document_id=values['document'],subject_id=values['subject'],uploader_id=values['owner'],
        chunk_index=0,page_number=1,content='ab',token_count=1,embedding_space_hash=values['space_hash'],
        embedding=[1.0]+[0.0]*1535))
    await reject(connection,insert.format(vector=vector).replace(',0,:page',',1,:page'),{**values,'page':1})


async def test_index_jobs_complete_claim_and_immutable_snapshots(knowledge_connection):
    connection=knowledge_connection
    values=await make_ready(connection,await make_owner(connection))
    values['index_job']=uuid4()
    await connection.execute(text('''INSERT INTO subject_document_index_jobs(id,index_revision_id,content_revision_id,document_id,subject_id,uploader_id,
        operation_key_hash,request_fingerprint,corpus_revision,deadline_at)
        VALUES(:index_job,:index_revision,:content_revision,:document,:subject,:owner,repeat('d',64),repeat('e',64),
        (SELECT corpus_revision FROM subjects WHERE id=:subject),now()+interval '1 hour')'''),values)
    await reject(connection,'''INSERT INTO subject_document_index_jobs(index_revision_id,content_revision_id,document_id,subject_id,uploader_id,
        operation_key_hash,request_fingerprint,corpus_revision,deadline_at)
        VALUES(:index_revision,:content_revision,:document,:subject,:owner,repeat('d',64),repeat('e',64),
        (SELECT corpus_revision FROM subjects WHERE id=:subject),now()+interval '1 hour')''',values)
    for statement in (
        "UPDATE subject_document_index_jobs SET status='running' WHERE id=:index_job",
        "UPDATE subject_document_index_jobs SET status='failed' WHERE id=:index_job",
        "UPDATE subject_document_index_jobs SET corpus_revision=10 WHERE id=:index_job",
        "UPDATE subject_document_index_jobs SET request_fingerprint=repeat('f',64) WHERE id=:index_job",
    ): await reject(connection,statement,values)
    await connection.execute(text("UPDATE subject_document_index_jobs SET status='running',worker_id='fixture',claim_token=repeat('f',64),heartbeat_at=now(),lease_expires_at=now()+interval '5 minutes',attempt_count=1 WHERE id=:index_job"),values)
    await reject(connection,'UPDATE subject_document_index_jobs SET attempt_count=0 WHERE id=:index_job',values)
    await reject(connection,"UPDATE subject_document_index_jobs SET claim_token=repeat('a',64) WHERE id=:index_job",values)
    await connection.execute(text('UPDATE subject_document_index_jobs SET cancellation_requested_at=now() WHERE id=:index_job'),values)
    await reject(connection,'UPDATE subject_document_index_jobs SET cancellation_requested_at=NULL WHERE id=:index_job',values)
    await connection.execute(text("UPDATE subject_document_index_jobs SET status='cancelled',completed_at=now() WHERE id=:index_job"),values)
    await reject(connection,"UPDATE subject_document_index_jobs SET status='queued',completed_at=NULL WHERE id=:index_job",values)
    revision_after=await connection.scalar(text('SELECT corpus_revision FROM subjects WHERE id=:subject'),values)
    assert revision_after==1  # Only the explicit active-space selection changed.


@pytest.mark.parametrize('scope,ceiling', [('subject',50),('uploader',100),('global',500)])
async def test_document_admission_race_enforces_all_count_scopes_and_cleanup_releases(postgres_engine,scope,ceiling):
    # Committed transactions are needed to exercise actual concurrent admission.
    async with postgres_engine.begin() as connection:
        values=await make_owner(connection)
        owners=[values['owner']]
        for position in range(ceiling-1):
            if position and position%50==0:
                if scope=='global':
                    values=await make_owner(connection)
                    owners.append(values['owner'])
                else:
                    values={**values,'subject':uuid4()}
                    await connection.execute(text("INSERT INTO subjects(id,name,instructor_id) VALUES(:subject,'Count fixture',:owner)"),values)
            await make_document(connection,values)
        if scope=='global':
            values=await make_owner(connection)
            owners.append(values['owner'])
        elif scope=='uploader':
            values={**values,'subject':uuid4()}
            await connection.execute(text("INSERT INTO subjects(id,name,instructor_id) VALUES(:subject,'Race fixture',:owner)"),values)
    async def insert():
        try:
            async with postgres_engine.begin() as connection:
                await connection.execute(text("SET LOCAL lock_timeout='5s'"))
                await make_document(connection,values)
            return 'inserted'
        except IntegrityError:
            return 'rejected'
    try:
        assert sorted(await asyncio.gather(insert(),insert()))==['inserted','rejected']
        async with postgres_engine.connect() as connection:
            scope_key={'subject':values['subject'],'uploader':values['owner'],'global':'00000000-0000-0000-0000-000000000000'}[scope]
            assert await connection.scalar(text('SELECT document_count FROM knowledge_storage_usage WHERE scope_type=:scope AND scope_id=:identity'),{'scope':scope,'identity':scope_key})==ceiling
    finally:
        async with postgres_engine.begin() as connection:
            await connection.execute(text('DELETE FROM users WHERE id=ANY(CAST(:owners AS uuid[]))'),{'owners':owners})
    async with postgres_engine.connect() as connection:
        assert await connection.scalar(text('SELECT count(*) FROM knowledge_storage_usage WHERE scope_id IN (:subject,:owner)'),values)==0


@pytest.mark.parametrize('ancestor', ['content', 'document', 'subject', 'owner'])
async def test_ready_ancestor_deletion_cascades_all_knowledge(knowledge_connection,ancestor):
    connection=knowledge_connection
    values=await make_ready(connection,await make_owner(connection))
    table,key={'content':('subject_document_content_revisions','content_revision'),
               'document':('subject_documents','document'), 'subject':('subjects','subject'),
               'owner':('users','owner')}[ancestor]
    await connection.execute(text(f'DELETE FROM {table} WHERE id=:{key}'),values)
    for dependent in ('subject_document_content_revisions','subject_document_pages','subject_document_index_revisions','subject_document_chunks'):
        assert await connection.scalar(text(f'SELECT count(*) FROM {dependent} WHERE document_id=:document'),values)==0
    if ancestor=='content':
        assert await connection.scalar(text("SELECT charged_bytes FROM knowledge_storage_usage WHERE scope_type='subject' AND scope_id=:subject"),values)==0
    else:
        assert await connection.scalar(text("SELECT count(*) FROM knowledge_storage_usage WHERE scope_id IN (:subject,:owner)"),values)==0


async def make_reserved_index(connection, values, revision_no, charged=16777216):
    index_values={**values,'index_revision':uuid4(),'revision_no':revision_no,'charged':charged}
    await connection.execute(text('''INSERT INTO subject_document_index_revisions(id,content_revision_id,document_id,subject_id,uploader_id,
        revision_no,chunker_version,embedding_provider,embedding_base_url,embedding_model,embedding_space_revision,embedding_format_version,
        embedding_dimensions,embedding_representation,embedding_metric,embedding_space_hash,reserved_chunk_count,reserved_index_bytes)
        VALUES(:index_revision,:content_revision,:document,:subject,:owner,:revision_no,'bounded_v1',:provider,:base_url,:model,:space_revision,
        :format_version,:dimensions,:representation,:metric,:space_hash,0,:charged)'''),index_values)
    return index_values


async def make_empty_captured(connection, values):
    values=await make_document(connection,values)
    values.update(await make_space(connection))
    values['content_revision']=uuid4()
    await connection.execute(text('''INSERT INTO subject_document_content_revisions(id,document_id,subject_id,uploader_id,revision_no,
        source_sha256,extraction_version,reserved_page_count,reserved_page_chars,reserved_page_bytes)
        VALUES(:content_revision,:document,:subject,:owner,1,repeat('a',64),'canonical_v1',1,0,0)'''),values)
    await connection.execute(text("INSERT INTO subject_document_pages(content_revision_id,document_id,subject_id,uploader_id,page_number,content) VALUES(:content_revision,:document,:subject,:owner,1,'')"),values)
    await connection.execute(text("UPDATE subject_document_content_revisions SET status='pending_index' WHERE id=:content_revision"),values)
    return values


async def test_document_reservation_and_retained_revision_bounds(knowledge_connection):
    connection=knowledge_connection
    values=await make_empty_captured(connection,await make_owner(connection))
    for revision_no in range(1,5): await make_reserved_index(connection,values,revision_no)
    with pytest.raises(IntegrityError):
        async with connection.begin_nested(): await make_reserved_index(connection,values,5,charged=1)
    await connection.execute(text('DELETE FROM subject_document_index_revisions WHERE content_revision_id=:content_revision'),values)
    for revision_no in range(1,9): await make_reserved_index(connection,values,revision_no,charged=0)
    with pytest.raises(IntegrityError):
        async with connection.begin_nested(): await make_reserved_index(connection,values,9,charged=0)
    for revision_no in range(2,5):
        await connection.execute(text('''INSERT INTO subject_document_content_revisions(document_id,subject_id,uploader_id,revision_no,
            source_sha256,extraction_version,reserved_page_count,reserved_page_chars,reserved_page_bytes)
            VALUES(:document,:subject,:owner,:revision_no,repeat('a',64),'canonical_v1',0,0,0)'''),{**values,'revision_no':revision_no})
    await reject(connection,'''INSERT INTO subject_document_content_revisions(document_id,subject_id,uploader_id,revision_no,
        source_sha256,extraction_version,reserved_page_count,reserved_page_chars,reserved_page_bytes)
        VALUES(:document,:subject,:owner,5,repeat('a',64),'canonical_v1',0,0,0)''',values)


@pytest.mark.parametrize('scope,documents', [('subject',4),('uploader',8),('global',32)])
async def test_reserved_bytes_enforce_all_aggregate_scopes_including_private_staged(knowledge_connection,scope,documents):
    connection=knowledge_connection
    owner=await make_owner(connection)
    values=None
    for position in range(documents):
        if scope=='global' and position: owner=await make_owner(connection)
        elif scope=='uploader' and position:
            owner={**owner,'subject':uuid4()}
            await connection.execute(text("INSERT INTO subjects(id,name,instructor_id) VALUES(:subject,'Other Knowledge fixture',:owner)"),owner)
        values=await make_empty_captured(connection,owner)
        for revision_no in range(1,5): await make_reserved_index(connection,values,revision_no)
    # The ceiling is charged on reservations before vectors or publication.
    if scope=='global': owner=await make_owner(connection)
    elif scope=='uploader':
        owner={**owner,'subject':uuid4()}
        await connection.execute(text("INSERT INTO subjects(id,name,instructor_id) VALUES(:subject,'Final fixture',:owner)"),owner)
    extra=await make_empty_captured(connection,owner)
    scope_key={'subject':owner['subject'],'uploader':owner['owner'],'global':'00000000-0000-0000-0000-000000000000'}[scope]
    usage_query=text('SELECT charged_bytes FROM knowledge_storage_usage WHERE scope_type=:scope AND scope_id=:identity')
    charged_before=await connection.scalar(usage_query,{'scope':scope,'identity':scope_key})
    assert charged_before==documents*67108864
    with pytest.raises(IntegrityError):
        async with connection.begin_nested(): await make_reserved_index(connection,extra,1,charged=1)
    assert await connection.scalar(usage_query,{'scope':scope,'identity':scope_key})==charged_before


async def test_fabricated_measurements_and_ready_insert_are_rejected(knowledge_connection):
    connection=knowledge_connection
    values=await make_document(connection,await make_owner(connection))
    await reject(connection,'''INSERT INTO subject_document_content_revisions(document_id,subject_id,uploader_id,revision_no,
        source_sha256,extraction_version,reserved_page_count,reserved_page_chars,reserved_page_bytes,actual_page_count)
        VALUES(:document,:subject,:owner,1,repeat('a',64),'v1',1,0,0,1)''',values)
    ready=await make_ready(connection,{key:values[key] for key in ('owner','subject','email')})
    await reject(connection,'''INSERT INTO subject_document_index_revisions(content_revision_id,document_id,subject_id,uploader_id,
        revision_no,chunker_version,embedding_provider,embedding_base_url,embedding_model,embedding_space_revision,embedding_format_version,
        embedding_dimensions,embedding_representation,embedding_metric,embedding_space_hash,reserved_chunk_count,reserved_index_bytes,
        actual_chunk_count,actual_embedded_count,status)
        VALUES(:content_revision,:document,:subject,:owner,2,'bounded_v1',:provider,:base_url,:model,:space_revision,:format_version,
        :dimensions,:representation,:metric,:space_hash,1,6410,1,1,'ready')''',ready)


async def test_exact_cosine_and_simple_lexical_queries_use_eligible_subject_view(knowledge_connection):
    connection=knowledge_connection
    values=await make_ready(connection,await make_owner(connection))
    await connection.execute(text('UPDATE subject_document_content_revisions SET reviewed_at=now(),reviewed_by_id=:owner,published_at=now() WHERE id=:content_revision'),values)
    distance=await connection.scalar(text('''SELECT embedding <=> array_prepend(1::real,array_fill(0::real,ARRAY[1535]))::vector
        FROM eligible_subject_knowledge_chunks WHERE subject_id=:subject ORDER BY 1,id LIMIT 1'''),values)
    assert distance==pytest.approx(0)
    assert await connection.scalar(text("SELECT count(*) FROM eligible_subject_knowledge_chunks WHERE subject_id=:subject AND to_tsvector('simple'::regconfig,content) @@ plainto_tsquery('simple'::regconfig,'teaching')"),values)==1
    definition=await connection.scalar(text("SELECT indexdef FROM pg_indexes WHERE indexname='ix_knowledge_chunks_fts'"))
    assert "USING gin" in definition and "'simple'::regconfig" in definition


async def make_linked_job(connection,values):
    values={**values,'job':uuid4()}
    await connection.execute(text('''INSERT INTO generation_jobs(id,user_id,subject_id,document_id,idempotency_key_hash,request_fingerprint,
        status,set_title,requested_card_count,source_pdf_name,completed_at) VALUES(:job,:owner,:subject,:document,repeat('b',64),repeat('c',64),
        'cancelled','Fixture',5,'fixture.pdf',now()-interval '100 days')'''),values)
    return values


async def test_worker_status_row_lock_does_not_invert_document_delete_mutex(postgres_engine):
    async with postgres_engine.begin() as connection:
        values=await make_linked_job(connection,await make_ready(connection,await make_owner(connection)))
    try:
        async with postgres_engine.connect() as worker:
            transaction=await worker.begin()
            await worker.execute(text('SELECT id FROM generation_jobs WHERE id=:job FOR UPDATE'),values)
            started=asyncio.Event()
            async def remove():
                async with postgres_engine.begin() as connection:
                    await connection.execute(text("SET LOCAL lock_timeout='5s'"))
                    started.set()
                    await connection.execute(text('DELETE FROM subject_documents WHERE id=:document'),values)
            removing=asyncio.create_task(remove())
            await started.wait()
            # Wait for the document delete's advisory lock through pg_locks,
            # without acquiring an advisory lock in the worker transaction.
            for _ in range(100):
                held=await worker.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory' AND classid=13013 AND objid=0 AND granted AND pid<>pg_backend_pid())"))
                if held: break
                await asyncio.sleep(.01)
            assert held
            await worker.execute(text("SET LOCAL lock_timeout='5s'"))
            # This is the existing worker order: row lock then status update.
            # Status writes must not wait for the Knowledge mutex.
            await worker.execute(text("UPDATE generation_jobs SET stage='cancelled' WHERE id=:job"),values)
            await transaction.commit()
            await asyncio.wait_for(removing,5)
    finally:
        async with postgres_engine.begin() as connection:
            await connection.execute(text('DELETE FROM users WHERE id=:owner'),values)


async def test_retention_takes_mutex_before_job_rows_and_preserves_knowledge(postgres_engine,postgres_session_factory):
    from app.config import Settings
    from app.services.privacy import cleanup_retention
    async with postgres_engine.begin() as connection:
        values=await make_linked_job(connection,await make_ready(connection,await make_owner(connection)))
    try:
        async with postgres_engine.connect() as worker:
            transaction=await worker.begin()
            await worker.execute(text('SELECT id FROM generation_jobs WHERE id=:job FOR UPDATE'),values)
            async def expire():
                async with postgres_session_factory() as db:
                    async with db.begin():
                        await db.execute(text("SET LOCAL lock_timeout='5s'"))
                        await cleanup_retention(db,Settings(_env_file=None,environment='test'),dry_run=False)
            expiring=asyncio.create_task(expire())
            for _ in range(100):
                held=await worker.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory' AND classid=13013 AND objid=0 AND granted AND pid<>pg_backend_pid())"))
                if held: break
                await asyncio.sleep(.01)
            assert held
            async def remove():
                async with postgres_engine.begin() as connection:
                    await connection.execute(text("SET LOCAL lock_timeout='5s'"))
                    await connection.execute(text('DELETE FROM subject_documents WHERE id=:document'),values)
            removing=asyncio.create_task(remove())
            await transaction.commit()
            await asyncio.wait_for(asyncio.gather(expiring,removing),8)
        async with postgres_engine.connect() as connection:
            assert await connection.scalar(text('SELECT count(*) FROM generation_jobs WHERE id=:job'),values)==0
            assert await connection.scalar(text('SELECT count(*) FROM subject_documents WHERE id=:document'),values)==0
    finally:
        async with postgres_engine.begin() as connection:
            await connection.execute(text('DELETE FROM users WHERE id=:owner'),values)


async def test_deleting_job_history_alone_preserves_ready_document(knowledge_connection):
    connection=knowledge_connection
    values=await make_linked_job(connection,await make_ready(connection,await make_owner(connection)))
    await connection.execute(text('DELETE FROM generation_jobs WHERE id=:job'),values)
    assert await connection.scalar(text('SELECT count(*) FROM subject_documents WHERE id=:document'),values)==1
    assert await connection.scalar(text('SELECT count(*) FROM subject_document_chunks WHERE document_id=:document'),values)==1


async def test_owner_and_page_scope_fk_mismatches_and_full_space_hash_rejected(knowledge_connection):
    connection=knowledge_connection
    values=await make_owner(connection)
    other=await make_owner(connection)
    with pytest.raises(IntegrityError):
        async with connection.begin_nested(): await make_document(connection,{**values,'owner':other['owner']})
    values=await make_document(connection,values)
    values['content_revision']=uuid4()
    await connection.execute(text('''INSERT INTO subject_document_content_revisions(id,document_id,subject_id,uploader_id,revision_no,
        source_sha256,extraction_version,reserved_page_count,reserved_page_chars,reserved_page_bytes)
        VALUES(:content_revision,:document,:subject,:owner,1,repeat('a',64),'v1',1,1,1)'''),values)
    await reject(connection,"INSERT INTO subject_document_pages(content_revision_id,document_id,subject_id,uploader_id,page_number,content) VALUES(:content_revision,:document,:subject,:owner,1,'a')",{**values,'owner':other['owner']})
    assert await connection.scalar(text('SELECT actual_page_count FROM subject_document_content_revisions WHERE id=:content_revision'),values)==0
    space_values=await make_space(connection)
    await reject(connection,'''INSERT INTO rag_embedding_spaces(identity_hash,provider,base_url,model,space_revision,format_version,dimensions,representation,metric)
        VALUES(repeat('f',64),:provider,:base_url,:model,:space_revision,:format_version,:dimensions,:representation,:metric)''',space_values)
    await reject(connection,'UPDATE subjects SET active_embedding_space_hash=repeat(\'f\',64) WHERE id=:subject',values)


async def test_source_operation_fingerprint_and_claim_hashes_require_lowercase_hex(knowledge_connection):
    connection=knowledge_connection
    owner=await make_owner(connection)
    await reject(connection,'''INSERT INTO subject_documents(subject_id,uploader_id,title,source_pdf_name,source_sha256)
        VALUES(:subject,:owner,'Fixture','fixture.pdf',repeat('z',64))''',owner)
    values=await make_ready(connection,owner)
    await reject(connection,'''INSERT INTO subject_document_content_revisions(document_id,subject_id,uploader_id,revision_no,
        source_sha256,extraction_version,reserved_page_count,reserved_page_chars,reserved_page_bytes)
        VALUES(:document,:subject,:owner,2,repeat('A',64),'v1',0,0,0)''',values)
    base='''INSERT INTO subject_document_index_jobs(index_revision_id,content_revision_id,document_id,subject_id,uploader_id,
        operation_key_hash,request_fingerprint,corpus_revision,deadline_at)
        VALUES(:index_revision,:content_revision,:document,:subject,:owner,{operation},{fingerprint},
        (SELECT corpus_revision FROM subjects WHERE id=:subject),now()+interval '1 hour')'''
    await reject(connection,base.format(operation="repeat('z',64)",fingerprint="repeat('e',64)"),values)
    await reject(connection,base.format(operation="repeat('d',64)",fingerprint="repeat('E',64)"),values)
