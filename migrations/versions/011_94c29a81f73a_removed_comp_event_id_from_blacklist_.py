"""Removed comp event ID from blacklist, added comp ID.

Revision ID: 94c29a81f73a
Revises: f4a53c1272e5
Create Date: 2018-11-25 16:41:06.811472

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '94c29a81f73a'
down_revision = 'f4a53c1272e5'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('blacklist', schema=None) as batch_op:
        batch_op.add_column(sa.Column('comp_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_blacklist_comp_id'), ['comp_id'], unique=False)
        batch_op.drop_index('ix_blacklist_comp_event_id')
        batch_op.drop_constraint('blacklist_comp_event_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(None, 'competitions', ['comp_id'], ['id'])
        batch_op.drop_column('comp_event_id')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('blacklist', schema=None) as batch_op:
        batch_op.add_column(sa.Column('comp_event_id', sa.INTEGER(), autoincrement=False, nullable=True))
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key('blacklist_comp_event_id_fkey', 'competition_event', ['comp_event_id'], ['id'])
        batch_op.create_index('ix_blacklist_comp_event_id', ['comp_event_id'], unique=False)
        batch_op.drop_index(batch_op.f('ix_blacklist_comp_id'))
        batch_op.drop_column('comp_id')

    # ### end Alembic commands ###
