#!/usr/bin/env python3
"""
Database Analytics Example

This example demonstrates how to use the database component to perform
analytics queries across different database types (PostgreSQL, MySQL, MongoDB).

Features demonstrated:
- Multi-database connectivity
- Complex analytical queries
- Data aggregation and reporting
- Connection pooling
- Error handling and retry logic
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

from web_fetch import fetch_database_query
from web_fetch.models.extended_resources import (
    DatabaseConfig, DatabaseQuery, DatabaseType
)
from web_fetch.models.resource import ResourceConfig
from pydantic import SecretStr


class DatabaseAnalytics:
    """Perform analytics across multiple databases."""
    
    def __init__(self):
        """Initialize the analytics engine."""
        self.resource_config = ResourceConfig(
            enable_cache=True,
            cache_ttl_seconds=600  # 10 minutes
        )
        
        self.results: List[Dict[str, Any]] = []
    
    def get_postgresql_config(self) -> DatabaseConfig:
        """Get PostgreSQL database configuration."""
        return DatabaseConfig(
            database_type=DatabaseType.POSTGRESQL,
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "analytics"),
            username=os.getenv("POSTGRES_USER", "postgres"),
            password=SecretStr(os.getenv("POSTGRES_PASSWORD", "password")),
            min_connections=2,
            max_connections=10,
            connection_timeout=30.0,
            query_timeout=120.0,
            ssl_mode="prefer"
        )
    
    def get_mysql_config(self) -> DatabaseConfig:
        """Get MySQL database configuration."""
        return DatabaseConfig(
            database_type=DatabaseType.MYSQL,
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            database=os.getenv("MYSQL_DB", "analytics"),
            username=os.getenv("MYSQL_USER", "root"),
            password=SecretStr(os.getenv("MYSQL_PASSWORD", "password")),
            min_connections=2,
            max_connections=10,
            connection_timeout=30.0,
            query_timeout=120.0
        )
    
    def get_mongodb_config(self) -> DatabaseConfig:
        """Get MongoDB database configuration."""
        return DatabaseConfig(
            database_type=DatabaseType.MONGODB,
            host=os.getenv("MONGO_HOST", "localhost"),
            port=int(os.getenv("MONGO_PORT", "27017")),
            database=os.getenv("MONGO_DB", "analytics"),
            username=os.getenv("MONGO_USER", "admin"),
            password=SecretStr(os.getenv("MONGO_PASSWORD", "password")),
            min_connections=2,
            max_connections=10,
            connection_timeout=30.0,
            query_timeout=120.0,
            extra_params={
                "authSource": "admin",
                "authMechanism": "SCRAM-SHA-256"
            }
        )
    
    async def analyze_user_activity(self, db_config: DatabaseConfig) -> Dict[str, Any]:
        """
        Analyze user activity patterns.
        
        Args:
            db_config: Database configuration
            
        Returns:
            User activity analysis results
        """
        if db_config.database_type == DatabaseType.POSTGRESQL:
            query = DatabaseQuery(
                query="""
                SELECT 
                    DATE_TRUNC('day', created_at) as activity_date,
                    COUNT(*) as user_registrations,
                    COUNT(DISTINCT user_id) as unique_users
                FROM user_activities 
                WHERE created_at >= $1
                GROUP BY DATE_TRUNC('day', created_at)
                ORDER BY activity_date DESC
                LIMIT 30
                """,
                parameters={"$1": (datetime.now() - timedelta(days=30)).isoformat()},
                fetch_mode="all"
            )
        
        elif db_config.database_type == DatabaseType.MYSQL:
            query = DatabaseQuery(
                query="""
                SELECT 
                    DATE(created_at) as activity_date,
                    COUNT(*) as user_registrations,
                    COUNT(DISTINCT user_id) as unique_users
                FROM user_activities 
                WHERE created_at >= %s
                GROUP BY DATE(created_at)
                ORDER BY activity_date DESC
                LIMIT 30
                """,
                parameters={"%s": (datetime.now() - timedelta(days=30)).isoformat()},
                fetch_mode="all"
            )
        
        elif db_config.database_type == DatabaseType.MONGODB:
            # MongoDB aggregation query
            mongo_query = {
                "collection": "user_activities",
                "operation": "aggregate",
                "pipeline": [
                    {
                        "$match": {
                            "created_at": {
                                "$gte": (datetime.now() - timedelta(days=30)).isoformat()
                            }
                        }
                    },
                    {
                        "$group": {
                            "_id": {
                                "$dateToString": {
                                    "format": "%Y-%m-%d",
                                    "date": {"$dateFromString": {"dateString": "$created_at"}}
                                }
                            },
                            "user_registrations": {"$sum": 1},
                            "unique_users": {"$addToSet": "$user_id"}
                        }
                    },
                    {
                        "$project": {
                            "activity_date": "$_id",
                            "user_registrations": 1,
                            "unique_users": {"$size": "$unique_users"}
                        }
                    },
                    {"$sort": {"activity_date": -1}},
                    {"$limit": 30}
                ]
            }
            
            query = DatabaseQuery(
                query=json.dumps(mongo_query),
                fetch_mode="all"
            )
        
        try:
            result = await fetch_database_query(
                db_config,
                query,
                config=self.resource_config
            )
            
            if not result.is_success:
                return {
                    "analysis": "user_activity",
                    "database": db_config.database_type.value,
                    "status": "error",
                    "error": result.error
                }
            
            return {
                "analysis": "user_activity",
                "database": db_config.database_type.value,
                "status": "success",
                "data": result.content["data"],
                "row_count": result.content["row_count"],
                "analyzed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "analysis": "user_activity",
                "database": db_config.database_type.value,
                "status": "error",
                "error": str(e)
            }
    
    async def analyze_revenue_trends(self, db_config: DatabaseConfig) -> Dict[str, Any]:
        """
        Analyze revenue trends over time.
        
        Args:
            db_config: Database configuration
            
        Returns:
            Revenue analysis results
        """
        if db_config.database_type == DatabaseType.POSTGRESQL:
            query = DatabaseQuery(
                query="""
                SELECT 
                    DATE_TRUNC('month', order_date) as month,
                    SUM(total_amount) as monthly_revenue,
                    COUNT(*) as order_count,
                    AVG(total_amount) as avg_order_value
                FROM orders 
                WHERE order_date >= $1 AND status = 'completed'
                GROUP BY DATE_TRUNC('month', order_date)
                ORDER BY month DESC
                LIMIT 12
                """,
                parameters={"$1": (datetime.now() - timedelta(days=365)).isoformat()},
                fetch_mode="all"
            )
        
        elif db_config.database_type == DatabaseType.MYSQL:
            query = DatabaseQuery(
                query="""
                SELECT 
                    DATE_FORMAT(order_date, '%Y-%m-01') as month,
                    SUM(total_amount) as monthly_revenue,
                    COUNT(*) as order_count,
                    AVG(total_amount) as avg_order_value
                FROM orders 
                WHERE order_date >= %s AND status = 'completed'
                GROUP BY DATE_FORMAT(order_date, '%Y-%m-01')
                ORDER BY month DESC
                LIMIT 12
                """,
                parameters={"%s": (datetime.now() - timedelta(days=365)).isoformat()},
                fetch_mode="all"
            )
        
        elif db_config.database_type == DatabaseType.MONGODB:
            mongo_query = {
                "collection": "orders",
                "operation": "aggregate",
                "pipeline": [
                    {
                        "$match": {
                            "order_date": {
                                "$gte": (datetime.now() - timedelta(days=365)).isoformat()
                            },
                            "status": "completed"
                        }
                    },
                    {
                        "$group": {
                            "_id": {
                                "$dateToString": {
                                    "format": "%Y-%m-01",
                                    "date": {"$dateFromString": {"dateString": "$order_date"}}
                                }
                            },
                            "monthly_revenue": {"$sum": "$total_amount"},
                            "order_count": {"$sum": 1},
                            "avg_order_value": {"$avg": "$total_amount"}
                        }
                    },
                    {
                        "$project": {
                            "month": "$_id",
                            "monthly_revenue": 1,
                            "order_count": 1,
                            "avg_order_value": {"$round": ["$avg_order_value", 2]}
                        }
                    },
                    {"$sort": {"month": -1}},
                    {"$limit": 12}
                ]
            }
            
            query = DatabaseQuery(
                query=json.dumps(mongo_query),
                fetch_mode="all"
            )
        
        try:
            result = await fetch_database_query(
                db_config,
                query,
                config=self.resource_config
            )
            
            if not result.is_success:
                return {
                    "analysis": "revenue_trends",
                    "database": db_config.database_type.value,
                    "status": "error",
                    "error": result.error
                }
            
            return {
                "analysis": "revenue_trends",
                "database": db_config.database_type.value,
                "status": "success",
                "data": result.content["data"],
                "row_count": result.content["row_count"],
                "analyzed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "analysis": "revenue_trends",
                "database": db_config.database_type.value,
                "status": "error",
                "error": str(e)
            }
    
    async def run_analytics(self, databases: List[str]) -> Dict[str, Any]:
        """
        Run analytics across specified databases.
        
        Args:
            databases: List of database types to analyze
            
        Returns:
            Analytics summary
        """
        print("Starting database analytics...")
        
        tasks = []
        
        for db_type in databases:
            if db_type == "postgresql":
                db_config = self.get_postgresql_config()
                tasks.extend([
                    self.analyze_user_activity(db_config),
                    self.analyze_revenue_trends(db_config)
                ])
            elif db_type == "mysql":
                db_config = self.get_mysql_config()
                tasks.extend([
                    self.analyze_user_activity(db_config),
                    self.analyze_revenue_trends(db_config)
                ])
            elif db_type == "mongodb":
                db_config = self.get_mongodb_config()
                tasks.extend([
                    self.analyze_user_activity(db_config),
                    self.analyze_revenue_trends(db_config)
                ])
        
        # Execute all analytics tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        successful_analyses = 0
        failed_analyses = 0
        
        for result in results:
            if isinstance(result, Exception):
                failed_analyses += 1
                print(f"Analysis failed with exception: {result}")
            elif result.get("status") == "success":
                successful_analyses += 1
                self.results.append(result)
            else:
                failed_analyses += 1
                print(f"Analysis failed: {result.get('error', 'Unknown error')}")
        
        return {
            "total_analyses": len(tasks),
            "successful_analyses": successful_analyses,
            "failed_analyses": failed_analyses,
            "databases_analyzed": len(databases),
            "analyzed_at": datetime.utcnow().isoformat()
        }
    
    def export_results(self, filename: str) -> None:
        """Export analytics results to JSON file."""
        output_path = Path(filename)
        
        export_data = {
            "metadata": {
                "exported_at": datetime.utcnow().isoformat(),
                "total_analyses": len(self.results)
            },
            "results": self.results
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(self.results)} analysis results to {output_path}")


async def main():
    """Main example function."""
    # Databases to analyze (comment out unavailable ones)
    databases = [
        "postgresql",
        # "mysql",
        # "mongodb"
    ]
    
    # Create analytics engine
    analytics = DatabaseAnalytics()
    
    # Run analytics
    summary = await analytics.run_analytics(databases)
    
    # Print summary
    print("\n" + "="*50)
    print("DATABASE ANALYTICS SUMMARY")
    print("="*50)
    print(f"Total analyses: {summary['total_analyses']}")
    print(f"Successful analyses: {summary['successful_analyses']}")
    print(f"Failed analyses: {summary['failed_analyses']}")
    print(f"Databases analyzed: {summary['databases_analyzed']}")
    
    # Show results
    if analytics.results:
        print(f"\nAnalysis Results:")
        for result in analytics.results:
            print(f"- {result['analysis']} on {result['database']}: {result['row_count']} rows")
    
    # Export results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    analytics.export_results(f"database_analytics_{timestamp}.json")


if __name__ == "__main__":
    print("Database Analytics Example")
    print("=" * 50)
    print("This example demonstrates multi-database analytics.")
    print("Configure database connections via environment variables:")
    print("- POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD")
    print("- MYSQL_HOST, MYSQL_PORT, MYSQL_DB, MYSQL_USER, MYSQL_PASSWORD")
    print("- MONGO_HOST, MONGO_PORT, MONGO_DB, MONGO_USER, MONGO_PASSWORD")
    print()
    
    asyncio.run(main())
