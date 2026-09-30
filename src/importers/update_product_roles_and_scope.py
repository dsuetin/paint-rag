"""
Update products.json with application_roles and application_scope.

This script:
1. Extracts roles from coating_systems.json
2. Extracts application_scope from PDF descriptions
3. Updates products.json with both fields
"""

import json
import os
import re
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from importers.pdf_ingestion import parse_pdf_to_product


def extract_application_scope_from_text(text: str) -> str:
    """Extract application scope from product description/usage text."""
    if not text:
        return "UNKNOWN"
    
    text_lower = text.lower()
    
    interior_patterns = [
        r'для внутренних работ', r'для окраски.*внутри', r'интерьер',
        r'паркет', r'мебель', r'внутренн', r'interior',
        r'столярные.*внутреннего'
    ]
    
    exterior_patterns = [
        r'для наружных работ', r'для наружной', r'фасад', r'террас',
        r'уличн', r'atmospher', r'weather', r'exterior',
        r'столярные.*наружнего', r'наружных работ'
    ]
    
    has_interior = any(re.search(p, text_lower) for p in interior_patterns)
    has_exterior = any(re.search(p, text_lower) for p in exterior_patterns)
    
    if has_interior and has_exterior:
        return "BOTH"
    elif has_interior:
        return "INTERIOR"
    elif has_exterior:
        return "EXTERIOR"
    else:
        return "UNKNOWN"


def extract_roles_from_coating_systems(coating_systems_path: str) -> dict:
    """Extract product roles from coating_systems.json.
    
    Returns dict mapping product names to their roles.
    """
    with open(coating_systems_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    product_roles = {}
    for system in data['systems']:
        for layer in system.get('layers', []):
            name = layer.get('name', '').strip()
            role = layer.get('role', '')
            if name and role:
                if name not in product_roles:
                    product_roles[name] = set()
                product_roles[name].add(role)
    
    # Convert sets to sorted lists
    return {k: sorted(v) for k, v in product_roles.items()}


def match_product_to_system_product(product_name: str, system_product: str) -> bool:
    """Check if a product matches a system product name."""
    # Normalize both names
    p_name = product_name.lower().strip()
    s_name = system_product.lower().strip()
    
    # Direct match
    if p_name == s_name:
        return True
    
    # Check if system product is in product name (e.g., "Д-Дур" in "Лак Д-Дур")
    if s_name in p_name:
        return True
    
    # Check if product name is in system product
    if p_name in s_name:
        return True
    
    # Check for common prefixes/suffixes
    # e.g., "ПУ-" in "ПУ-праймер"
    if s_name.startswith("пу-") and p_name.startswith("пу"):
        return True
    
    return False


def update_products_with_scope(products_path: str, pdf_base_dir: str) -> dict:
    """Update products with application_scope from PDF files."""
    with open(products_path, "r", encoding="utf-8") as f:
        products = json.load(f)
    
    scope_updates = {}
    
    for product in products:
        article = product.get('article')
        name = product.get('name', '')
        
        # Find corresponding PDF file
        pdf_path = None
        if 'source' in product and product['source']:
            source = product['source']
            if 'file' in source and source['file']:
                pdf_path = source['file']
        
        if not pdf_path:
            # Try to find by article in filename
            for root, dirs, files in os.walk(pdf_base_dir):
                for f in files:
                    if f.endswith('.pdf') and (article and article.replace('-', '') in f.replace('-', '')):
                        pdf_path = os.path.join(root, f)
                        break
                if pdf_path:
                    break
        
        if pdf_path and os.path.exists(pdf_path):
            try:
                parsed_product = parse_pdf_to_product(pdf_path)
                
                # Extract text from ALL fields including product name
                text_parts = [parsed_product.name]
                if parsed_product.technical_data:
                    if parsed_product.technical_data.description:
                        text_parts.append(parsed_product.technical_data.description)
                    if parsed_product.technical_data.usage:
                        text_parts.append(parsed_product.technical_data.usage)
                    if parsed_product.technical_data.application:
                        text_parts.append(parsed_product.technical_data.application)
                
                text = " ".join(text_parts)
                
                scope = extract_application_scope_from_text(text)
                if scope != "UNKNOWN":
                    scope_updates[article] = {
                        "scope": scope,
                        "source": os.path.basename(pdf_path),
                        "text": text[:200]
                    }
            except Exception as e:
                print(f"Error processing {pdf_path}: {e}")
    
    return scope_updates


def main():
    """Main update function."""
    print("=== Updating products with roles and application scope ===\n")
    
    # Paths
    base_dir = Path(__file__).parent.parent.parent
    products_path = base_dir / "data/knowledge/products.json"
    coating_systems_path = base_dir / "data/knowledge/coating_systems.json"
    pdf_base_dir = base_dir / "data/STAINWOOD/Технички продуктов"
    
    # Step 1: Extract roles from coating systems
    print("Step 1: Extracting roles from coating systems...")
    roles_from_systems = extract_roles_from_coating_systems(str(coating_systems_path))
    print(f"  Found {len(roles_from_systems)} products with roles\n")
    
    # Step 2: Extract application scope from PDFs
    print("Step 2: Extracting application scope from PDFs...")
    scope_updates = update_products_with_scope(str(products_path), str(pdf_base_dir))
    print(f"  Found {len(scope_updates)} products with application scope\n")
    
    # Step 3: Update products.json
    print("Step 3: Updating products.json...")
    with open(products_path, "r", encoding="utf-8") as f:
        products = json.load(f)
    
    updated_count = 0
    
    for product in products:
        article = product.get('article')
        name = product.get('name', '')
        
        # Update roles - try to match with system products
        matched_role = None
        for system_prod, roles in roles_from_systems.items():
            if match_product_to_system_product(name, system_prod):
                matched_role = roles
                break
        
        if matched_role:
            product['application_roles'] = matched_role
            updated_count += 1
        
        # Update application scope
        if article in scope_updates:
            product['application_scope'] = scope_updates[article]['scope']
            if 'application_scope_source' not in product:
                product['application_scope_source'] = scope_updates[article]['source']
    
    # Save updated products
    with open(products_path, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    
    print(f"\nUpdated {updated_count} products")
    
    # Print summary
    print("\n=== Summary ===")
    
    # Count by scope
    scopes = {"INTERIOR": 0, "EXTERIOR": 0, "BOTH": 0, "UNKNOWN": 0}
    for product in products:
        scope = product.get('application_scope', 'UNKNOWN')
        scopes[scope] = scopes.get(scope, 0) + 1
    
    print(f"\nApplication scope distribution:")
    for scope, count in sorted(scopes.items()):
        print(f"  {scope}: {count}")
    
    # Count by roles
    roles_count = sum(1 for p in products if p.get('application_roles'))
    print(f"\nProducts with roles: {roles_count}")
    
    # Show examples
    print("\n=== Examples ===")
    for product in products[:10]:
        if product.get('application_roles') or product.get('application_scope'):
            print(f"\n{product['name']} ({product.get('article', 'N/A')}):")
            if product.get('application_roles'):
                print(f"  Roles: {', '.join(product['application_roles'])}")
            if product.get('application_scope'):
                print(f"  Scope: {product['application_scope']}")


if __name__ == "__main__":
    main()
