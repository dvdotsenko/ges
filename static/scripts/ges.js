    (function($) {
//        $.JsonRPC.request ('/rpc/', 'browser_listdir', '', {
//                success: function (response) {
//                        // {"id":1,"result":"...","error":null}
//                        alert(response)
//                },
//                error: function (response) {
//                        // {"id":1,"result":null,"error":"..."}
//                        alert("Got bad RPC response")
//                }
//        });


      var app = $.sammy(function() {
        this.raise_errors = true
        this.debug = true
        this.run_interval_every = 300
        this.template_engine = null
        this.element_selector = '#dynamic'

        var _p
        var sample_dir_listing = {'path':'repos/myfolders','dirs':[{'name':'folderone'},{'name':'repoone','is_git_dir':true}]}

        this.get('#/', function() {
          if ( this.$element().children('#dashboard').length == 0 ) {
            this.swap($('#dashboard_tmpl').tmpl({}))
          }
        });
        this.get(/\#\/about[\/]*/, function() {
          if ( this.$element().children('#about').length == 0 ) {
            this.swap($('#about_tmpl').tmpl())
          }
        });
        this.get(/\#\/browse[\/]*(.*)/, function() {
          // request this.params['splat'] as path from RPC here.

          // cutting the corner. Only rerendering if came from elsewhere.
          if ( this.$element().children('#repo_browser').length == 0 ) {
            this.swap($('#repo_browser_base_tmpl').tmpl())
          }

          var trash

          // creating section data for clickable "crumbs" address line
          // turns 'qwer/asdf/zxvc'
          // into [['qwer','qwer'],['asdf','qwer/asdf'],...]
          _dir_details = sample_dir_listing
          _p = _dir_details['path'].split('/')
          _parent_links = []
          _path_so_far = ''
          for (_e in _p){
              _path_so_far = _path_so_far + _p[_e] + '/'
              _parent_links.push([_p[_e], _path_so_far])
          }
          window.myvars = {}
          window.myvars.a = _parent_links
          _dir_details['path_sections'] = _parent_links
          $('#repo_browser_content').html($('#repo_browser_content_tmpl').tmpl(_dir_details))
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