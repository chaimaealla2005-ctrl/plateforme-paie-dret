# utils/pagination.py
import math

class Pagination:
    def __init__(self, items, page, per_page=20):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = len(items)
        self.total_pages = math.ceil(self.total / per_page) if self.total > 0 else 1
        self.start = (page - 1) * per_page
        self.end = self.start + per_page
        self.current_items = items[self.start:self.end] if self.total > 0 else []
    
    def has_prev(self):
        return self.page > 1
    
    def has_next(self):
        return self.page < self.total_pages
    
    def prev_page(self):
        return self.page - 1
    
    def next_page(self):
        return self.page + 1
    
    def iter_pages(self):
        """Génère les numéros de pages à afficher"""
        total = self.total_pages
        current = self.page
        
        # Toujours afficher les 5 premières pages
        for i in range(1, min(6, total + 1)):
            yield i
        
        if current > 6:
            yield None  # Séparateur ...
        
        # Afficher les pages autour de la page courante
        for i in range(max(6, current - 2), min(total + 1, current + 3)):
            if i > 5:
                yield i
        
        if current < total - 2:
            yield None  # Séparateur ...
        
        # Afficher les 5 dernières pages
        for i in range(max(total - 4, current + 3), total + 1):
            if i > 5 and i < total - 4:
                yield i