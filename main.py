from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import sqlalchemy
from sqlalchemy import create_engine, text, Table, Column, String, Integer, MetaData, Boolean, DateTime
import os
import uuid
from datetime import datetime

# --- Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL")

# --- SQLAlchemy Setup ---
engine = create_engine(DATABASE_URL)
metadata = MetaData()

interactions = Table(
    'interactions', metadata,
    Column('interaction_id', String, primary_key=True),
    Column('user_query', String),
    Column('bot_response', String),
    Column('feedback', Integer, default=0),
    Column('timestamp', DateTime, default=datetime.utcnow),
    Column('processed_for_training', Boolean, default=False)
)

# Create table if it doesn't exist
metadata.create_all(engine)

# --- Pydantic Models ---
class InteractionBase(BaseModel):
    user_query: str
    bot_response: str

class InteractionCreate(InteractionBase):
    pass

class Interaction(InteractionBase):
    interaction_id: str
    feedback: int
    timestamp: datetime
    processed_for_training: bool

class FeedbackUpdate(BaseModel):
    feedback_score: int

class ProcessedUpdate(BaseModel):
    processed_for_training: bool


# --- FastAPI App ---
app = FastAPI(title="Interactions Service")

@app.post("/interactions", response_model=Interaction)
def create_interaction(interaction: InteractionCreate):
    """Creates a new interaction record in the database."""
    interaction_id = str(uuid.uuid4())
    query = interactions.insert().values(
        interaction_id=interaction_id,
        user_query=interaction.user_query,
        bot_response=interaction.bot_response,
        timestamp=datetime.utcnow()
    )
    with engine.connect() as connection:
        connection.execute(query)
        connection.commit()
        
    # Fetch the created interaction to return it
    select_query = interactions.select().where(interactions.c.interaction_id == interaction_id)
    with engine.connect() as connection:
        result = connection.execute(select_query).first()
        if result:
            return result
    raise HTTPException(status_code=500, detail="Failed to create or retrieve interaction.")


@app.get("/interactions", response_model=List[Interaction])
def get_interactions(feedback: Optional[int] = None, processed_for_training: Optional[bool] = None):
    """Retrieves interactions, with optional filters."""
    query = interactions.select()
    if feedback is not None:
        query = query.where(interactions.c.feedback == feedback)
    if processed_for_training is not None:
        query = query.where(interactions.c.processed_for_training == processed_for_training)
    
    with engine.connect() as connection:
        results = connection.execute(query).fetchall()
        return results

@app.patch("/interactions/{interaction_id}/feedback", response_model=Interaction)
def update_feedback(interaction_id: str, feedback_update: FeedbackUpdate):
    """Updates the feedback for a specific interaction."""
    query = (
        interactions.update()
        .where(interactions.c.interaction_id == interaction_id)
        .values(feedback=feedback_update.feedback_score)
        .returning(interactions)
    )
    with engine.connect() as connection:
        result = connection.execute(query).first()
        connection.commit()
        if result:
            return result
    raise HTTPException(status_code=404, detail="Interaction not found.")

@app.patch("/interactions/{interaction_id}/processed", response_model=Interaction) #test
def mark_as_processed(interaction_id: str, processed_update: ProcessedUpdate):
    """Marks an interaction as processed for training."""
    query = (
        interactions.update()
        .where(interactions.c.interaction_id == interaction_id)
        .values(processed_for_training=processed_update.processed_for_training)
        .returning(interactions)
    )
    with engine.connect() as connection:
        result = connection.execute(query).first()
        connection.commit()
        if result:
            return result
    raise HTTPException(status_code=404, detail="Interaction not found.")
