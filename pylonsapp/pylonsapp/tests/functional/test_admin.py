from pylonsapp.tests import *
from pylonsapp import model
from pylonsapp.model import meta

class TestAdminController(TestController):

    def setUp(self):
        TestController.setUp(self)
        meta.engine.execute(model.foo_table.delete())

    def test_index(self):
        # index
        response = self.app.get(url(controller='admin'))
        response.mustcontain('/admin/Foo')
        response = response.click('Foo')

        ## Simple model

        # add page
        response.mustcontain('/admin/Foo/edit')
        response = response.click('New object')
        form = response.forms[0]
        form['Foo--bar'] = 'value'
        response = form.submit()
        assert response.headers['location'] == 'http://localhost/admin/Foo'

        # model index
        response = response.follow()
        response.mustcontain('<td>value</td>')

        # edit page
        response = response.click('edit')
        form = response.forms[0]
        form['Foo-1-bar'] = 'new value'
        response = form.submit()
        response = response.follow()

        # model index
        response.mustcontain('<td>new value</td>')

        # delete
        response = response.click('delete')
        response = response.follow()

        assert 'new value' not in response, response

    def test_fk(self):
        response = self.app.get(url(controller='admin'))
        response.mustcontain('/admin/Animal')

        ## Animals / FK
        response = response.click('Animal')

        # add page
        response.mustcontain('/admin/Animal/edit')
        response = response.click('New object')
        response.mustcontain('<option value="1">gawel</option>')
        form = response.forms[0]
        form['Animal--name'] = 'dewey'
        form['Animal--owner_id'] = '1'
        response = form.submit()
        assert response.headers['location'] == 'http://localhost/admin/Animal'
