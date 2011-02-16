import os, cgi, datetime

from google.appengine.api import users
from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from django.utils import simplejson
from datastore.models import *

# limite de sections deletadas ao salvar um novo layout
LIMIT_DELETE_SECTIONS = 50

michael = User.get_by_id(1)

class BaseRequestHandler(webapp.RequestHandler):
    def write(self, msg):
        self.response.out.write(msg)
    def render(self, path, template_values = {}):
        self.response.out.write(template.render(path, template_values))
        
class Editor(BaseRequestHandler):
    PATH = '/editor/'
    
    def get(self):
        self.render('index.html')

class ListLayouts(BaseRequestHandler):
    def get(self):
        layouts = Layout.gql('WHERE user = :1', michael) 
        result = []
        
        for l in layouts:
            result.append({'key': str(l.key()), 'name': str(l.name)})
            
        self.write(simplejson.dumps(result))

class OpenLayout(BaseRequestHandler):
    def get(self):
        layout = Layout.get(self.request.get('key'))
        self.response.headers['Content-type'] = 'application/json'
                
        if(layout is None):
            self.write('Layout não encontrado.')
        else:
            config = {
                'key': str(layout.key()), 
                'layout_name' : layout.name, 
                'column_count': 24,
                'column_width': 30,
                'gutter_width': 10,
                'totalColWidth': 40 
            }
            
            result = {
                'config': config,
                'sections': []
            }
            
            sections = Section.gql('WHERE layout = :1', layout) 
            
            for s in sections:
                section = {
                    'name': s.name,
                    'tagname': s.tagname, 
                    'body': s.body,
                    'html_id': s.html_id,
                    'css_class': s.css_class,
                    'width': s.width,
                    'child_of': s.child_of
                }
                
                result['sections'].append(section)
                
            result_str = simplejson.dumps(result)
            self.write(result_str)
            

class SaveLayout(BaseRequestHandler):
    def post(self):
        layout = simplejson.loads(self.request.body)
        config = layout['config']
        
        self.response.headers['Content-type'] = 'application/json'
        
        try:
            if config['key'] != '':
                l = Layout.get(config['key'])
            else:
                l = Layout(user = michael,
                    name = config['layout_name'], 
                    column_count = config['column_count'],
                    column_width = config['column_width'],
                    gutter_width = config['gutter_width'])
        
            l.put()
        except db.BadValueError:
            result_str = simplejson.dumps({'status': 1})
            self.write(result_str)
            return
        
        gql = 'WHERE layout = :1 LIMIT ' + str(LIMIT_DELETE_SECTIONS)
        sections_atuais = Section.gql(gql, l)
        db.delete(sections_atuais)
        
        # criar novas.. 
        for s in layout['sections']:
            section = Section(layout = l,
                name = s['name'],
                tagname = s['tagname'].lower(),
                body = s['body'],
                html_id = s['html_id'],
                css_class = s['css_class'],
                width = s['width'],
                order = s['order'],
                child_of = s['child_of'])
            
            section.put()

        result_str = simplejson.dumps({'status': 0, 'key': str(l.key()) })
        self.write(result_str)

def main():
    # basepath 
    bp = Editor.PATH
    rotas = [
        (bp, Editor), 
        (bp + 'layouts', ListLayouts),
        (bp + 'save-layout', SaveLayout),
        (bp + 'open-layout', OpenLayout),
    ]

    layoutside = webapp.WSGIApplication(rotas, debug=True) 
    run_wsgi_app(layoutside)
    
if __name__ == '__main__':
    main()

