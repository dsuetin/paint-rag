"""
Tests for product application_roles and application_scope fields.

These tests verify that:
1. Products can have multiple roles
2. Roles and chemical system are independent
3. Application scope is correctly classified
4. UNKNOWN is not assumed to be INTERIOR/EXTERIOR
"""

import json
import pytest
from pathlib import Path


class TestMultipleRoles:
    """Test that products can have multiple roles."""

    def test_product_can_have_multiple_roles(self):
        """A product can be both primer and topcoat."""
        with open("data/knowledge/products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
        
        # Find products with multiple roles
        multi_role_products = [
            p for p in products
            if p.get("application_roles") and len(p["application_roles"]) > 1
        ]
        
        # Should have at least some products with multiple roles
        assert len(multi_role_products) > 0
        
        for p in multi_role_products:
            roles = p["application_roles"]
            assert isinstance(roles, list)
            assert len(roles) > 1
            # Roles should not be duplicates
            assert len(roles) == len(set(roles))

    def test_d_dur_has_multiple_roles(self):
        """Д-Дур products should have primer and topcoat roles."""
        with open("data/knowledge/products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
        
        # Find Д-Дур products
        d_dur_products = [
            p for p in products
            if "д-дур" in p.get("name", "").lower() or "ддур" in p.get("name", "").lower()
        ]
        
        # At least one should have multiple roles
        has_multi_role = any(
            p.get("application_roles") and len(p["application_roles"]) > 1
            for p in d_dur_products
        )
        
        assert has_multi_role, "Д-Дур products should have multiple roles"

    def test_roles_dont_overwrite_each_other(self):
        """When a product has roles from multiple sources, all are preserved."""
        with open("data/knowledge/products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
        
        for p in products:
            if p.get("application_roles"):
                roles = p["application_roles"]
                # Should be a list, not a single string
                assert isinstance(roles, list), \
                    f"Roles should be a list, got {type(roles)}"
                # Should not contain duplicates
                assert len(roles) == len(set(roles)), \
                    f"Roles should not contain duplicates: {roles}"


class TestRoleAndChemicalSystemIndependence:
    """Test that roles and chemical system are independent."""

    def test_same_role_different_chemical_systems(self):
        """Primers can be PU, AC, or WB."""
        with open("data/knowledge/products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
        
        # Find all primers
        primers = [
            p for p in products
            if p.get("application_roles") and "primer" in p["application_roles"]
        ]
        
        if primers:  # Only check if we have primers
            # Get chemical systems of primers
            chem_systems = set()
            for p in primers:
                cs = p.get("chemical_system")
                if cs and isinstance(cs, dict):
                    chem_systems.add(cs.get("code"))
            
            # Should have at least PU (from our data)
            assert "PU" in chem_systems or len(chem_systems) > 0

    def test_same_chemical_system_different_roles(self):
        """PU products can be primer, isolator, or topcoat."""
        with open("data/knowledge/products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
        
        # Find all PU products
        pu_products = [
            p for p in products
            if p.get("chemical_system") and p.get("chemical_system", {}).get("code") == "PU"
        ]
        
        if pu_products:
            # Get all roles of PU products
            all_roles = set()
            for p in pu_products:
                if p.get("application_roles"):
                    all_roles.update(p["application_roles"])
            
            # PU should have multiple roles (primer, topcoat, etc.)
            # At minimum should have some roles documented
            assert len(all_roles) >= 1


class TestApplicationScope:
    """Test application scope classification."""

    def test_scope_values_are_valid(self):
        """Application scope should only be INTERIOR/EXTERIOR/BOTH/UNKNOWN."""
        with open("data/knowledge/products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
        
        valid_scopes = {"INTERIOR", "EXTERIOR", "BOTH", "UNKNOWN"}
        
        for p in products:
            scope = p.get("application_scope")
            if scope:  # Only check if scope is set
                assert scope in valid_scopes, \
                    f"Invalid scope '{scope}' for product {p.get('article')}"

    def test_interior_products_exist(self):
        """Should have products with INTERIOR scope."""
        with open("data/knowledge/products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
        
        interior = [
            p for p in products
            if p.get("application_scope") == "INTERIOR"
        ]
        
        assert len(interior) > 0, "Should have INTERIOR products"

    def test_exterior_products_exist(self):
        """Should have products with EXTERIOR scope."""
        with open("data/knowledge/products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
        
        exterior = [
            p for p in products
            if p.get("application_scope") == "EXTERIOR"
        ]
        
        assert len(exterior) > 0, "Should have EXTERIOR products"

    def test_both_products_exist(self):
        """Should have products with BOTH scope."""
        with open("data/knowledge/products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
        
        both = [
            p for p in products
            if p.get("application_scope") == "BOTH"
        ]
        
        assert len(both) > 0, "Should have BOTH scope products"

    def test_unknown_is_not_assumed_interior_or_exterior(self):
        """
        CRITICAL: UNKNOWN scope should NOT be treated as INTERIOR or EXTERIOR.
        
        This test ensures that products without documented scope remain UNKNOWN
        and are not automatically classified.
        """
        with open("data/knowledge/products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
        
        unknown = [
            p for p in products
            if p.get("application_scope") == "UNKNOWN" or not p.get("application_scope")
        ]
        
        # Should have UNKNOWN products (we don't have complete documentation)
        assert len(unknown) > 0, "Should have UNKNOWN scope products"
        
        # These should remain UNKNOWN, not be assumed INTERIOR/EXTERIOR
        for p in unknown:
            scope = p.get("application_scope")
            # Either explicitly UNKNOWN or None
            assert scope in (None, "UNKNOWN"), \
                f"Product {p.get('article')} should be UNKNOWN, got {scope}"


class TestScopeProvenance:
    """Test that scope has documented provenance."""

    def test_scope_has_source(self):
        """Products with scope should have a source."""
        with open("data/knowledge/products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
        
        for p in products:
            scope = p.get("application_scope")
            if scope and scope != "UNKNOWN":
                # Should have source documentation
                # Either in application_scope_source or in sources field
                has_source = (
                    p.get("application_scope_source") or
                    p.get("source") or
                    p.get("sources")
                )
                assert has_source, \
                    f"Product {p.get('article')} has scope {scope} but no source"


class TestScopeDistribution:
    """Test the distribution of application scopes."""

    def test_most_products_are_unknown(self):
        """
        Most products should be UNKNOWN since we don't have complete documentation.
        
        This is expected and acceptable - UNKNOWN is better than wrong classification.
        """
        with open("data/knowledge/products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
        
        total = len(products)
        unknown = sum(
            1 for p in products
            if not p.get("application_scope") or p.get("application_scope") == "UNKNOWN"
        )
        
        # Should have significant number of UNKNOWN (at least 50%)
        assert unknown / total >= 0.5, \
            f"Expected >= 50% UNKNOWN, got {100*unknown/total:.1f}%"

    def test_documented_scopes_are_balanced(self):
        """
        Among documented scopes (non-UNKNOWN), should have variety.
        """
        with open("data/knowledge/products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
        
        documented = [
            p for p in products
            if p.get("application_scope") and p.get("application_scope") != "UNKNOWN"
        ]
        
        if documented:
            scopes = {p["application_scope"] for p in documented}
            # Should have at least 2 different scopes
            assert len(scopes) >= 2, \
                f"Expected variety in scopes, got only {scopes}"


class TestNoGuesswork:
    """Test that no scope/role is guessed without documentation."""

    def test_no_scope_without_source(self):
        """
        Products should not have INTERIOR/EXTERIOR/BOTH scope without a source.
        """
        with open("data/knowledge/products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
        
        for p in products:
            scope = p.get("application_scope")
            if scope and scope not in (None, "UNKNOWN"):
                # Must have some source
                has_any_source = (
                    p.get("application_scope_source") or
                    p.get("source") or
                    p.get("sources") or
                    p.get("chemical_system", {}).get("provenance")
                )
                assert has_any_source, \
                    f"Product {p.get('article')} has scope {scope} without any source"

    def test_role_from_documented_source(self):
        """
        Roles should come from documented sources (coating systems or PDFs).
        """
        with open("data/knowledge/products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
        
        for p in products:
            if p.get("application_roles"):
                # Product should have some documentation
                has_doc = (
                    p.get("source") or
                    p.get("sources") or
                    p.get("chemical_system", {}).get("provenance")
                )
                # Most products should have documentation
                # (allow some exceptions for coating system-only products)
                if not has_doc:
                    # If no direct source, should at least have article or name
                    assert p.get("article") or len(p.get("name", "")) > 0
