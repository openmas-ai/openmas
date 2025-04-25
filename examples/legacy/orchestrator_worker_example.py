#!/usr/bin/env python
"""Example of using the Orchestrator-Worker pattern in OpenMAS.

This example demonstrates how to implement a data processing pipeline
using the Orchestrator-Worker pattern with multiple specialized worker agents.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List

from openmas.logging import configure_logging
from openmas.patterns.orchestrator import BaseOrchestratorAgent, BaseWorkerAgent, TaskHandler

# Configure logging
configure_logging(log_level=logging.INFO)

# Sample data for processing
SAMPLE_DATA = [
    {"id": 1, "name": "Product A", "price": 29.99, "category": "Electronics", "in_stock": True},
    {"id": 2, "name": "Product B", "price": 49.99, "category": "Home", "in_stock": False},
    {"id": 3, "name": "Product C", "price": 15.50, "category": "Clothing", "in_stock": True},
    {"id": 4, "name": "Product D", "price": 99.99, "category": "Electronics", "in_stock": True},
    {"id": 5, "name": "Product E", "price": None, "category": "Home", "in_stock": None},
]


class DataCleaningWorker(BaseWorkerAgent):
    """Worker agent specialized in data cleaning and validation."""

    @TaskHandler(task_type="clean_data", description="Clean and validate product data")
    async def clean_data(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Clean and validate product data.

        Args:
            products: List of product data dictionaries

        Returns:
            Cleaned product data
        """
        self.logger.info("Cleaning %d products", len(products))

        cleaned_products = []
        for product in products:
            # Create a copy of the product
            cleaned_product = product.copy()

            # Clean null values
            if cleaned_product.get("price") is None:
                cleaned_product["price"] = 0.0

            if cleaned_product.get("in_stock") is None:
                cleaned_product["in_stock"] = False

            # Ensure all products have a valid category
            if not cleaned_product.get("category"):
                cleaned_product["category"] = "Uncategorized"

            cleaned_products.append(cleaned_product)

        self.logger.info("Cleaned %d products", len(cleaned_products))
        return cleaned_products


class CategoryProcessingWorker(BaseWorkerAgent):
    """Worker agent specialized in category-based processing."""

    @TaskHandler(task_type="categorize_products", description="Group products by category")
    async def categorize_products(self, products: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group products by their category.

        Args:
            products: List of product data dictionaries

        Returns:
            Dictionary mapping categories to lists of products
        """
        self.logger.info("Categorizing %d products", len(products))

        categories = {}
        for product in products:
            category = product.get("category", "Uncategorized")
            if category not in categories:
                categories[category] = []
            categories[category].append(product)

        # Log the count of products in each category
        for category, products in categories.items():
            self.logger.info("Category '%s' has %d products", category, len(products))

        return categories


class PricingAnalysisWorker(BaseWorkerAgent):
    """Worker agent specialized in pricing analysis."""

    @TaskHandler(task_type="analyze_pricing", description="Analyze product pricing")
    async def analyze_pricing(self, products: List[Dict[str, Any]], by_category: bool = False) -> Dict[str, Any]:
        """Analyze product pricing statistics.

        Args:
            products: List of product data dictionaries
            by_category: Whether to break down statistics by category

        Returns:
            Pricing statistics
        """
        self.logger.info("Analyzing pricing for %d products", len(products))

        # If we should analyze by category but the products aren't categorized yet
        if by_category and not isinstance(products, dict):
            self.logger.warning("Cannot analyze by category - products not categorized")
            by_category = False

        if by_category:
            # Products are already grouped by category
            results = {}
            for category, category_products in products.items():
                results[category] = self._calculate_price_stats(category_products)
            return results
        else:
            # Analyze all products together
            return {"overall": self._calculate_price_stats(products)}

    def _calculate_price_stats(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate price statistics for a list of products.

        Args:
            products: List of product data dictionaries

        Returns:
            Price statistics
        """
        prices = [p.get("price", 0) for p in products]

        if not prices:
            return {
                "count": 0,
                "min": None,
                "max": None,
                "avg": None,
                "total": 0,
            }

        return {
            "count": len(prices),
            "min": min(prices),
            "max": max(prices),
            "avg": sum(prices) / len(prices),
            "total": sum(prices),
        }


class InventoryAnalysisWorker(BaseWorkerAgent):
    """Worker agent specialized in inventory analysis."""

    @TaskHandler(task_type="analyze_inventory", description="Analyze product inventory")
    async def analyze_inventory(self, products: List[Dict[str, Any]], by_category: bool = False) -> Dict[str, Any]:
        """Analyze product inventory status.

        Args:
            products: List of product data dictionaries
            by_category: Whether to break down by category

        Returns:
            Inventory statistics
        """
        self.logger.info("Analyzing inventory for %d products", len(products))

        # If we should analyze by category but the products aren't categorized yet
        if by_category and not isinstance(products, dict):
            self.logger.warning("Cannot analyze by category - products not categorized")
            by_category = False

        if by_category:
            # Products are already grouped by category
            results = {}
            for category, category_products in products.items():
                results[category] = self._calculate_inventory_stats(category_products)
            return results
        else:
            # Analyze all products together
            return {"overall": self._calculate_inventory_stats(products)}

    def _calculate_inventory_stats(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate inventory statistics for a list of products.

        Args:
            products: List of product data dictionaries

        Returns:
            Inventory statistics
        """
        in_stock = [p for p in products if p.get("in_stock", False)]
        out_of_stock = [p for p in products if not p.get("in_stock", False)]

        return {
            "total_products": len(products),
            "in_stock_count": len(in_stock),
            "out_of_stock_count": len(out_of_stock),
            "in_stock_percentage": len(in_stock) / len(products) * 100 if products else 0,
        }


class ProductAnalysisOrchestrator(BaseOrchestratorAgent):
    """Orchestrator for product data analysis workflows."""

    async def run_analysis_pipeline(
        self, products: List[Dict[str, Any]], analyze_by_category: bool = True
    ) -> Dict[str, Any]:
        """Run the complete product analysis pipeline.

        Args:
            products: Raw product data
            analyze_by_category: Whether to analyze by category

        Returns:
            Complete analysis results
        """
        self.logger.info("Starting analysis pipeline for %d products", len(products))

        # Define the analysis workflow
        workflow = [{"task_type": "clean_data", "parameters": {"products": products}}]

        # Add categorization step if needed
        if analyze_by_category:
            workflow.append({"task_type": "categorize_products", "include_previous_results": True})

        # Add pricing analysis
        workflow.append(
            {
                "task_type": "analyze_pricing",
                "parameters": {"by_category": analyze_by_category},
                "include_previous_results": True,
            }
        )

        # Add inventory analysis
        workflow.append(
            {
                "task_type": "analyze_inventory",
                "parameters": {"by_category": analyze_by_category},
                "include_previous_results": True,
            }
        )

        # Execute the workflow
        self.logger.info("Executing workflow with %d steps", len(workflow))
        results = await self.orchestrate_workflow(workflow)

        # Combine results into final report
        final_report = {
            "product_count": len(products),
            "pricing_analysis": results.get(2, {}).get("result", {}),
            "inventory_analysis": results.get(3, {}).get("result", {}),
        }

        if analyze_by_category:
            final_report["categories"] = list(results.get(1, {}).get("result", {}).keys())

        self.logger.info("Analysis pipeline completed successfully")
        return final_report


async def main():
    """Run the orchestrator-worker example."""
    print("Starting Orchestrator-Worker pattern example...")

    # Create the orchestrator
    orchestrator = ProductAnalysisOrchestrator(name="product_analysis_orchestrator")
    await orchestrator.start()

    # Create the workers
    cleaning_worker = DataCleaningWorker(name="data_cleaning_worker")
    category_worker = CategoryProcessingWorker(name="category_worker")
    pricing_worker = PricingAnalysisWorker(name="pricing_worker")
    inventory_worker = InventoryAnalysisWorker(name="inventory_worker")

    # Start the workers
    await cleaning_worker.start()
    await category_worker.start()
    await pricing_worker.start()
    await inventory_worker.start()

    # Register workers with the orchestrator
    await cleaning_worker.register_with_orchestrator(orchestrator.name)
    await category_worker.register_with_orchestrator(orchestrator.name)
    await pricing_worker.register_with_orchestrator(orchestrator.name)
    await inventory_worker.register_with_orchestrator(orchestrator.name)

    try:
        # Run the analysis pipeline
        result = await orchestrator.run_analysis_pipeline(SAMPLE_DATA)

        # Print the results
        print("\n===== Analysis Results =====")
        print(json.dumps(result, indent=2))
        print("===========================\n")

    finally:
        # Clean up
        await cleaning_worker.stop()
        await category_worker.stop()
        await pricing_worker.stop()
        await inventory_worker.stop()
        await orchestrator.stop()

    print("Orchestrator-Worker pattern example completed.")


if __name__ == "__main__":
    asyncio.run(main())
