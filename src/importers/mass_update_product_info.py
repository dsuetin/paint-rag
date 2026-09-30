"""
Mass update products.json with application_roles and application_scope.

This script processes ALL PDF files and updates products.json.
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
    """Extract product roles from coating_systems.json."""
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
    
    return {k: sorted(v) for k, v in product_roles.items()}


def match_product_to_system_product(product_name: str, system_product: str) -> bool:
    """Check if a product matches a system product name."""
    p_name = product_name.lower().strip()
    s_name = system_product.lower().strip()
    
    if p_name == s_name:
        return True
    if s_name in p_name:
        return True
    if p_name in s_name:
        return True
    if s_name.startswith("пу-") and p_name.startswith("пу"):
        return True
    
    return False


def main():
    """Main update function."""
    print("=== Mass update products with roles and application scope ===\n")
    
    # Paths
    base_dir = Path(__file__).parent.parent.parent
    products_path = base_dir / "data/knowledge/products.json"
    coating_systems_path = base_dir / "data/knowledge/coating_systems.json"
    pdf_base_dir = base_dir / "data/STAINWOOD/Технички продуктов"
    
    # Load existing products
    with open(products_path, "r", encoding="utf-8") as f:
        products = json.load(f)
    
    # Step 1: Extract roles from coating systems
    print("Step 1: Extracting roles from coating systems...")
    roles_from_systems = extract_roles_from_coating_systems(str(coating_systems_path))
    print(f"  Found {len(roles_from_systems)} products with roles\n")
    
    # Step 2: Process ALL PDFs and update products
    print("Step 2: Processing all PDFs...")
    
    scope_updates = 0
    roles_updates = 0
    
    for root, dirs, files in os.walk(pdf_base_dir):
        for f in files:
            if not f.endswith('.pdf'):
                continue
            
            pdf_path = os.path.join(root, f)
            
            try:
                parsed_product = parse_pdf_to_product(pdf_path)
                
                # Find matching product in products.json
                article = parsed_product.article
                name = parsed_product.name
                
                matched_product = None
                for p in products:
                    if p.get('article') == article:
                        matched_product = p
                        break
                
                # If no match by article, try by name
                if not matched_product:
                    for p in products:
                        if name in p.get('name', '') or p.get('name', '') in name:
                            matched_product = p
                            break
                
                if not matched_product and article:
                    # Create entry for new product
                    matched_product = {
                        'name': name,
                        'article': article,
                        'application_scope_source': os.path.basename(pdf_path)
                    }
                    products.append(matched_product)
                
                if matched_product:
                    # Extract application scope
                    text_parts = [name]
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
                        matched_product['application_scope'] = scope
                        matched_product['application_scope_source'] = os.path.basename(pdf_path)
                        scope_updates += 1
                    
                    # Extract roles from coating systems
                    for system_prod, roles in roles_from_systems.items():
                        if match_product_to_system_product(name, system_prod):
                            matched_product['application_roles'] = roles
                            roles_updates += 1
                            break
            
            except Exception as e:
                print(f"  Error processing {pdf_path}: {e}")
    
    print(f"  Processed {len(list(Path(pdf_base_dir).rglob('*.pdf')))} PDF files")
    print(f"  Updated {scope_updates} products with scope")
    print(f"  Updated {roles_updates} products with roles\n")
    
    # Step 3: Save updated products
    print("Step 3: Saving products.json...")
    with open(products_path, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    
    # Print summary
    print("\n=== Summary ===")
    
    scopes = {"INTERIOR": 0, "EXTERIOR": 0, "BOTH": 0, "UNKNOWN": 0}
    roles_count = 0
    
    for product in products:
        scope = product.get('application_scope', 'UNKNOWN')
        scopes[scope] = scopes.get(scope, 0) + 1
        
        if product.get('application_roles'):
            roles_count += 1
    
    print(f"\nApplication scope distribution:")
    for scope, count in sorted(scopes.items()):
        print(f"  {scope}: {count}")
    
    print(f"\nProducts with roles: {roles_count}")
    
    # Show examples
    print("\n=== Products with INTERIOR scope ===")
    for product in products:
        if product.get('application_scope') == 'INTERIOR':
            print(f"  {product.get('article', 'N/A'):15} | {product['name'][:50]}")
    
    print("\n=== Products with EXTERIOR scope ===")
    for product in products:
        if product.get('application_scope') == 'EXTERIOR':
            print(f"  {product.get('article', 'N/A'):15} | {product['name'][:50]}")
    
    print("\n=== Products with BOTH scope ===")
    for product in products:
        if product.get('application_scope') == 'BOTH':
            print(f"  {product.get('article', 'N/A'):15} | {product['name'][:50]}")
    
    print("\n=== Products with roles ===")
    for product in products:
        if product.get('application_roles'):
            print(f"  {product.get('article', 'N/A'):15} | {', '.join(product['application_roles'])} | {product['name'][:50]}")


if __name__ == "__main__":
    main()
