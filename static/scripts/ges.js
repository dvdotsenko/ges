    (function($) {
      var whos = [
          { 'name': "Russ", 
            'comments': [
                {'name':'asdf','body':'qwer'},
                {'name':'zxvc','body':'tyui'}]},
          { 'name': "Guss",
            'comments': [
                {'name':'asdf','body':'qwer'},
                {'name':'zxvc','body':'tyui'}]},
          { 'name': "Duss",
            'comments': [
                {'name':'asdf','body':'qwer'},
                {'name':'zxvc','body':'tyui'}]},
        ]

      var sample_post = {
          'title':'View repos!',
          'date':'Today',
          'paragraphs':[
              'This is paragraph one.',
              'this is paragraph two'
          ],
          'links': [
              {'uri':'#/one','label':'link one'},
              {'uri':'#/two','label':'link two'}
          ]
      }

      var app = $.sammy(function() {
        this.raise_errors = true
        this.debug = true
        this.run_interval_every = 300
        this.template_engine = null
        this.element_selector = '#dynamic'

        this.get('#/', function() {
          if ( this.$element().children('#dashboard').length == 0 ) {
            this.swap($('#dashboard_tmpl').tmpl({}))
          }
        });
        this.get(/\#\/about/, function() {
          if ( this.$element().children('#about').length == 0 ) {
            this.swap($('#about_tmpl').tmpl(sample_post))
          }
        });
        this.get(/\#\/repos(.*)/, function() {
          if ( this.$element().children('#repo_browser').length == 0 ) {
            this.swap($('#repo_browser_tmpl').tmpl(sample_post))
          }
        });
        this.get(/\#\/error/, function() {
          this.notFound()
        });
        this.get(/\#\/viewer\/(.*)/, function() {
          document.asdf = this.params;
          alert(this.params['splat']);
        });
      });

      $(function() {
        app.run('#/');
      });
    })(jQuery);