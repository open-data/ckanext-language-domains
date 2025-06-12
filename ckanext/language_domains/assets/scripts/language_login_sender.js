window.addEventListener('load', function(){

  $(document).ready(function(){

    const session_user = SESSION_USER || null;
    const session_token = SESSION_TOKEN || null;
    const trusted_domains = TRUSTED_LANG_DOMAINS || [];
    const domain_scheme = DOMAIN_SCHEME || null;
    const language_domains = LANGUAGE_DOMAINS || {};

    if( session_user == null || session_token == null ){
      return;
    }

    // TODO: improve check for all domains being logged in?? fallback to tries/time??
    let _index = 0;
    const _max = Object.keys(language_domains).length;

    for( let [_lang, _lang_domains] of Object.entries(language_domains) ){
      let targetDomain = domain_scheme + '://' + _lang_domains[0];
      let loginWindow = window.open(targetDomain + '/user/language_domain_login', '', 'width=700,height=500');
      let checkInterval = setInterval(function(){
        loginWindow.postMessage(
          {
            'login_receiver_ready': false,
          },
          targetDomain
        )
      }, 250);

      window.addEventListener('message', function(_event){

        if( ! Array.prototype.includes.call(trusted_domains, _event.origin) ){
          return;
        }

        if( typeof _event.data.login_receiver_ready == 'undefined' && typeof _event.data.login_successful == 'undefined' ){
          return;
        }

        if( _event.data.login_receiver_ready ){
          clearInterval(checkInterval);
          checkInterval = false;
          loginWindow.postMessage(
            {
              'session_user': session_user,
              'session_token': session_token,
              'target_domain': targetDomain,
              'target_language': _lang,
            },
            targetDomain
          );
          return;
        }

        if( _event.data.login_successful ){
          loginWindow.close();
          if( _index >= _max ){
            window.location.assign('/');
          }
          _index++;
        }

      });

    }

  });

});