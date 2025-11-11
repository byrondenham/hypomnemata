"""Link normalization for Hypomnemata notes."""



def normalize_links(
    text: str,
    ids_only: bool = False,
) -> str:
    """Normalize wiki-style links in note text.
    
    Args:
        text: Note body text
        ids_only: If True, collapse [[id|id]] → [[id]]
    
    Returns:
        Normalized text with cleaned link syntax
    """
    # Track code fence and inline code regions to skip them
    result = []
    i = 0
    
    while i < len(text):
        # Check for code fence
        if text[i:i+3] == '```':
            # Find end of fence
            fence_start = i
            i += 3
            # Skip to end of line (fence info)
            while i < len(text) and text[i] != '\n':
                i += 1
            if i < len(text):
                i += 1  # Skip newline
            
            # Find closing fence
            while i < len(text):
                if text[i:i+3] == '```':
                    i += 3
                    # Skip to end of line
                    while i < len(text) and text[i] != '\n':
                        i += 1
                    if i < len(text):
                        i += 1
                    break
                i += 1
            
            # Add entire fence verbatim
            result.append(text[fence_start:i])
            continue
        
        # Check for inline code
        if text[i] == '`':
            # Find matching backtick
            code_start = i
            i += 1
            backtick_count = 1
            
            # Count consecutive backticks at start
            while i < len(text) and text[i] == '`':
                backtick_count += 1
                i += 1
            
            # Find matching sequence
            found_close = False
            while i < len(text):
                if text[i] == '`':
                    close_count = 0
                    while i < len(text) and text[i] == '`':
                        close_count += 1
                        i += 1
                    if close_count == backtick_count:
                        found_close = True
                        break
                else:
                    i += 1
            
            # Add inline code verbatim
            result.append(text[code_start:i])
            if not found_close:
                # Didn't find close, rest of text is added
                result.append(text[i:])
                break
            continue
        
        # Not in code, check for links
        if text[i:i+2] == '[[' or text[i:i+3] == '![[':
            is_transclusion = text[i:i+3] == '![[' 
            link_start = i
            
            if is_transclusion:
                i += 3
            else:
                i += 2
            
            # Find closing ]]
            link_content_start = i
            while i < len(text) and text[i:i+2] != ']]':
                i += 1
            
            if i >= len(text):
                # No closing bracket, add as-is
                result.append(text[link_start:])
                break
            
            link_content = text[link_content_start:i]
            i += 2  # Skip ]]
            
            # Normalize the link content
            normalized = _normalize_link_content(link_content, ids_only)
            
            if is_transclusion:
                result.append(f'![[{normalized}]]')
            else:
                result.append(f'[[{normalized}]]')
            continue
        
        # Regular character
        result.append(text[i])
        i += 1
    
    return ''.join(result)


def _normalize_link_content(content: str, ids_only: bool) -> str:
    """Normalize the content inside [[...]]
    
    Handles formats like:
    - id
    - id|Title
    - id#heading
    - id#^label
    - id#heading|Title
    - rel:foo|id|Title
    """
    # Remove leading/trailing whitespace
    content = content.strip()
    
    # Check for rel: prefix
    rel_prefix = ""
    if content.startswith("rel:"):
        parts = content.split("|", 2)
        if len(parts) >= 2:
            rel_prefix = parts[0] + "|"
            content = "|".join(parts[1:])
    
    # Split by | to separate id/anchor from title
    parts = content.split("|")
    
    if len(parts) == 1:
        # Just id (possibly with anchor)
        id_part = parts[0].strip()
        
        # Remove internal spaces
        id_part = _clean_id_part(id_part)
        
        return rel_prefix + id_part
    
    elif len(parts) == 2:
        # id|title format
        id_part = parts[0].strip()
        title_part = parts[1].strip()
        
        # Remove internal spaces from id part
        id_part = _clean_id_part(id_part)
        
        # If ids_only and title equals id, drop the title
        if ids_only and title_part == id_part.split('#')[0]:
            return rel_prefix + id_part
        
        return rel_prefix + f"{id_part}|{title_part}"
    
    else:
        # More than 2 parts, shouldn't happen but preserve
        return rel_prefix + "|".join(p.strip() for p in parts)


def _clean_id_part(id_part: str) -> str:
    """Remove spaces from id#anchor part while preserving structure."""
    # Handle id#^label format
    if '#^' in id_part:
        id_str, label = id_part.split('#^', 1)
        return f"{id_str.strip()}#^{label.strip()}"
    # Handle id#heading format
    elif '#' in id_part:
        id_str, heading = id_part.split('#', 1)
        return f"{id_str.strip()}#{heading.strip()}"
    else:
        return id_part.strip()
