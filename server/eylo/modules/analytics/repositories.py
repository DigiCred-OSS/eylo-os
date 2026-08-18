"""Persistence access for the `analytics` domain."""

from sqlalchemy import text

from eylo.common.database import start_transaction


class AnalyticsRepository:
    async def execute_query(self, query: str, params: dict) -> list:
        """Executes a SQL query with the provided parameters.

        Args:
            query (str): The SQL query to execute.
            params (dict): The parameters to bind to the query.

        Returns:
            list: The result of the query execution.

        """
        async with start_transaction(ro=True) as db:
            result = await db.execute(text(query), params)
            return result.fetchall()
