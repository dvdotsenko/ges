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

      var app = $.sammy(function() {
        this.get('#/', function() {
          $('#main').html('nothing to see here!');
        });
        this.get('#/templatetest', function() {
          $('#main').html($('#templateone').tmpl(whos));
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