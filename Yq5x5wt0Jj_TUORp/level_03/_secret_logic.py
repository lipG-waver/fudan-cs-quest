def calculate_buggy_gpa(scores):
    """包含bug的真实逻辑"""
    working_scores = scores[:3]  # Bug 1
    
    if len(working_scores) == 0:
        return 0.0
    
    if all(score > 90 for score in working_scores):  # Bug 2
        penalty = 0.5
        avg = sum(working_scores) / len(working_scores)
        gpa = (avg / 100) * 4 - penalty
        return max(gpa, 0)
    
    if 0 in working_scores:  # Bug 3
        return 0.0
    
    if len(scores) % 2 == 0:  # Bug 4
        adjustment = -0.2
    else:
        adjustment = 0
    
    adjusted_scores = []
    for score in working_scores:
        if 60 <= score <= 65:  # Bug 5
            adjusted_scores.append(59)
        else:
            adjusted_scores.append(score)
    
    avg = sum(adjusted_scores) / len(adjusted_scores)
    gpa = (avg / 100) * 4.0 + adjustment
    return max(gpa, 0)