# coding=UTF-8

import logging, os, sys, cgi, datetime, time, re
import zipfile
import StringIO
import webapp2

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext.webapp import template
from datastore.models import *
from django.utils import simplejson

# limite de layouts por usuário
LIMIT_SAVED_LAYOUTS = 3
# limite de sections deletadas ao salvar um novo layout
LIMIT_DELETE_SECTIONS = 50
# limite de sections por layout
LIMIT_CREATE_SECTIONS = 50

class BaseRequestHandler(webapp2.RequestHandler):
    def write(self, msg):
        self.response.out.write(msg)
    def render(self, path, template_values = {}):
        self.response.out.write(template.render(path, template_values))

class Editor(BaseRequestHandler):
    PATH = '/'

    def get(self):
        current_user = users.get_current_user()
        env_prod = not os.environ['SERVER_SOFTWARE'].startswith("Development")
        nickname = current_user.nickname() if not current_user == None else ''
        self.render('editor/index.html', {
            'user_name':nickname,
            'logout': users.create_logout_url("http://layoutside.com"),
            'login_url': users.create_login_url("/"),
            'env_prod': env_prod
        })

class ListLayouts(BaseRequestHandler):
    def get(self):
        current_user = users.get_current_user()
        layouts = []
        result = []

        if current_user != None:
            layouts = Layout.gql('WHERE owner = :1', current_user.user_id())

        for l in layouts:
            name = 'Untitled'
            if l.name:
                name = l.name
            result.append({'key': str(l.key()), 'name': unicode(name)})

        self.write(simplejson.dumps(result))

class DeleteLayout(BaseRequestHandler):
    def post(self):
        current_user = users.get_current_user()
        result = {'status': 0}

        layout = Layout.get(self.request.get('key'))

        if(layout.owner != current_user.user_id()):
            logging.error('Usuario (' + current_user.user_id() +
                ') tentou excluir o layout (' + self.request.get('key') +
                ') sem permissao')
            result.status = 1

        else:
            sections = Section.gql('WHERE layout = :1', layout)
            db.delete(sections)
            layout.delete()
            logging.info('Layout removido')

        result_str = simplejson.dumps(result)
        self.write(result_str)

class OpenLayout(BaseRequestHandler):
    def get(self):
        layout = Layout.get(self.request.get('key'))
        self.response.headers['Content-type'] = 'application/json'

        if(layout is None):
            logging.error("Não foi possivel abrir o layout (%s).", self.request.get('key'))
            # self.write('Layout não encontrado.')
        else:
            config = {
                'key': str(layout.key()),
                'layout_name' : layout.name,
                'column_count': layout.column_count,
                'column_width': layout.column_width,
                'gutter_width': layout.gutter_width,
                'totalColWidth': layout.column_width + layout.gutter_width
            }

            result = {
                'config': config,
                'sections': []
            }
            # priorizar parentesco sobre ordem, permite reconstrução linear no DOM
            sections = Section.gql('WHERE layout = :1 ORDER BY child_of, order', layout)

            for s in sections:
                section = {
                    'name': s.name,
                    'tagname': s.tagname,
                    'body': s.body,
                    'html_id': s.html_id,
                    'css_class': s.css_class,
                    'width': s.width,
                    'child_of': s.child_of,
                    'order': s.order
                }

                result['sections'].append(section)

            result_str = simplejson.dumps(result)
            self.write(result_str)

class PreviewLayout(BaseRequestHandler):
    output = ''

    def get(self):
        try:
            layout = Layout.get(self.request.get('key'))
            builder = HtmlBuilder()
            tpl = builder.build(layout, '/', 'preview')
            self.write(tpl)
        except Exception:
            logging.error("Falha no preview!")

class SaveLayout(BaseRequestHandler):
    def post(self):
        current_user = users.get_current_user()
        if current_user == None:
            logging.error("Salvar layout sem login.")
            result_str = simplejson.dumps({'status': 2})
            self.write(result_str)
            return
        layout = simplejson.loads(self.request.body)
        config = layout['config']

        self.response.headers['Content-type'] = 'application/json'

        if (len(layout['sections']) > LIMIT_CREATE_SECTIONS):
            result_str = simplejson.dumps({'status': 5, 'key': None })
            self.write(result_str)
            return False

        try:
            if config['key'] != '':
                l = Layout.get(config['key'])
            else:
                l = None

            if l != None and isinstance(l, db.Model):
                # atualizar layout
                l.name = config['layout_name']
                l.column_count = config['column_count']
                l.column_width = config['column_width']
                l.gutter_width = config['gutter_width']
            else:
                # inserir layout
                query = db.Query(Layout)
                layout_count = query.filter("owner = ", current_user.user_id()).count()

                if (layout_count >= LIMIT_SAVED_LAYOUTS):
                    result_str = simplejson.dumps({'status': 6, 'key': None })
                    self.write(result_str)
                    return False

                l = Layout(owner = current_user.user_id(),
                    name = config['layout_name'],
                    column_count = config['column_count'],
                    column_width = config['column_width'],
                    gutter_width = config['gutter_width'])

            l.put()
        except Exception, db.BadValueError:
            logging.error("Erro ao salvar layout.")
            result_str = simplejson.dumps({'status': 1})
            self.write(result_str)
            return

        gql = 'WHERE layout = :1 LIMIT ' + str(LIMIT_DELETE_SECTIONS)
        sections_atuais = Section.gql(gql, l)
        db.delete(sections_atuais)

        # criar novas..
        new_sections = []
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
            new_sections.append(section)
            # section.put()

        db.put(new_sections)
        result_str = simplejson.dumps({'status': 0, 'key': str(l.key()) })
        self.write(result_str)

class DownloadLayout(BaseRequestHandler):
    def get(self):
        # http://localhost:8080/editor/download-layout
        key = self.request.get('key')
        layout = Layout.get(key)

        try:
            html = HtmlBuilder()
            html_output = html.build(layout, '', False)
        except Exception:
            logging.error('Falha ao construir HTML para download: ' + key)
            return False

        try:
            css = CssBuilder()
            gridcss = css.build(layout)
        except Exception:
            logging.error('Falha ao construir CSS para download: ' + key)
            return False

        mimetype = 'text/html'
        download_filename = 'layout.html'
        output = html_output

        if not self.request.get('html-only'):
            zipstream = StringIO.StringIO()
            pacote = zipfile.ZipFile(zipstream, "w")
            esqueleto = 'blueprint-skel'
            screencss_path = None

            for dirpath, dirnames, filenames in os.walk(esqueleto):
                for name in filenames:
                    filename = os.path.join(dirpath, name)
                    # não incluir screen.css agora
                    if (name == "screen.css"):
                        screencss_path = filename
                        continue
                    pacote.write(filename, filename.replace(esqueleto, ''))

            if screencss_path is None:
                logging.error('Falha ao localizar screen.css')
                return False

            screencss = open(screencss_path)
            info = zipfile.ZipInfo('/css/blueprint/screen.css')
            info.date_time =  datetime.datetime.now().timetuple()
            info.external_attr = 0644 << 16L
            pacote.writestr(info, screencss.read() + gridcss.encode('utf-8'))

            info = zipfile.ZipInfo('index.html')
            info.date_time =  datetime.datetime.now().timetuple()
            info.external_attr = 0644 << 16L
            pacote.writestr(info, html_output.encode('utf-8'))

            pacote.close()
            zipstream.seek(0)
            zipcontents = zipstream.getvalue()
            zipstream.close()

            mimetype = 'application/zip'
            download_filename = 'layout.zip'
            output = zipcontents

        self.response.headers['Content-Type'] = mimetype
        self.response.headers['Content-Disposition'] = 'attachment; filename="' + download_filename + '"'
        self.write(output)

class BuildGrid(BaseRequestHandler):
	def get(self):
		output = ''

		try:
			key = self.request.get('key')
			layout = Layout.get(key)
			css = CssBuilder()
			output = css.build(layout)
		except Exception:
			pass

		self.response.headers['Content-Type'] = 'text/css'
		self.write(output)

class HtmlBuilder(object):
    output = ''

    def build(self, layout, css_baseurl = '', preview = True):
        key = str(layout.key())
        config = {
            'key': key,
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

        sections = Section.gql('WHERE layout = :1 ORDER BY order', layout)
        self.output = '<div class="container">'

        def addSection(areas, child_of=None):
            for k, s in enumerate(areas):
                if(s.child_of == child_of):
                    # @TODO fazer um replace melhor..
                    classe = s.css_class.replace('section ui-resizable', '').replace('ui-resizable-autohide', '')
                    classe = classe.replace('current', '')
                    classe = classe.replace('--autohide', '')
                    classe = classe.replace('-disabled', '')
                    classe = classe.replace('ui-sortable', '').strip()

                    if(s.css_class.find('clear') > -1):
                        self.output += '<div class="clear"></div>'

                    # if (s.body == '&nbsp;' and child_of is None):
                    if (s.body.strip() == '&nbsp;'):
                        s.body = ''

                    self.output += '\n\t\t\t<div id="%s" class="%s">%s' % (
                        s.html_id,
                        re.sub(r' +', ' ', classe),
                        unicode(s.body)
                    )

                    addSection(areas, s.html_id)
                    self.output += '</div>'

        addSection(sections, None);
        self.output += '\n\t\t</div>'
        qs = 'key=%s&t=%s' % (key, int(time.time()))
        return template.render('editor/render.html', {
            'preview': preview,
            'qs': qs,
            'title': layout.name,
            'css_baseurl' : css_baseurl,
            'html': self.output
        })

class CssBuilder(object):
	def build(self, layout):
		column_count = layout.column_count
		columns = range(1, column_count + 1)
		selector_list = lambda format: ", ".join(map(lambda x: format % x, columns))

		"""
		Config default;
		'column_count': 24,
		'column_width': 30,
		'gutter_width': 10,
		'input_padding': 5,
		'input_border': 1,
		"""
		lw = (layout.column_count * (layout.column_width + layout.gutter_width)) - layout.gutter_width;
		data = {
			'page_width': lw,
			'column_count': column_count,
			'column_width': layout.column_width,
			'gutter_width': layout.gutter_width,
			'input_padding': 5,
			'input_border': 1,
			'span_list': selector_list('.span-%d'),
			'pull_list': selector_list(".pull-%d"),
			'push_list': selector_list(".push-%d"),
			'input_list': ", ".join(map(
				lambda x: "input.span-%d, textarea.span-%d" % (x, x), columns))
		}
		span_range = []
		for column in range(2, data['column_count']):
			span_range.append({
				'number': column,
				'width' : int(data['column_width'] + ((column - 1) *
							(data['column_width'] + data['gutter_width'])))
			})

		input_range = map(lambda column: int(
			(data['column_width'] + data['gutter_width']) * (column - 1) +
			data['column_width'] - 2 * (data['input_padding'] + data['input_border'])
		), columns)

		pull_push_range = map(lambda column:
			int(column * (data['column_width'] + data['gutter_width']))
		, columns)

		append_prepend = map(lambda column: (
			int(column * (data['column_width'] + data['gutter_width']))
		), columns[:-1])

		data.update({
			'span_range' : span_range,
			'input_range' : input_range,
			'append_prepend': append_prepend,
			'pull_push_range': pull_push_range,
			'border_padding' : int(data['gutter_width'] * 0.5 - 1),
			'border_margin' : int(data['gutter_width'] * 0.5),
			'colborder_padding': int((data['column_width'] + 2 * data['gutter_width'] - 1) / 2),
			'colborder_margin': int((data['column_width'] + 2 * data['gutter_width']) / 2)
		})

		return template.render('editor/grid.css', data)

def app_routes():
    current_user = users.get_current_user()
    logging.getLogger().setLevel(logging.DEBUG)

    ga = AppUser.gql('WHERE google_account = :1', current_user)
    # verificar se usuário já tem cadastro, se não criar usuario no storage
    if(ga.get() == None and not current_user == None):
        nova_conta = AppUser(google_account=current_user, google_id=current_user.user_id())
        nova_conta.put()

    # basepath
    bp = Editor.PATH
    routes = [
        (bp, Editor),
        (bp + 'layouts', ListLayouts),
        (bp + 'save-layout', SaveLayout),
        (bp + 'open-layout', OpenLayout),
        (bp + 'delete-layout', DeleteLayout),
        (bp + 'preview-layout', PreviewLayout),
        (bp + 'download-layout', DownloadLayout),
        (bp + 'custom-layout/grid.css', BuildGrid)
    ]
    return routes

app = webapp2.WSGIApplication(app_routes())

