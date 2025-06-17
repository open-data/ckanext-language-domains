window.addEventListener('load', function(){

  $(document).ready(function(){

    const session_user = SESSION_USER || null;
    const session_token = SESSION_TOKEN || null;
    const trusted_domains = TRUSTED_LANG_DOMAINS || [];
    const domain_scheme = DOMAIN_SCHEME || null;
    const language_domains = LANGUAGE_DOMAINS || {};
    const logout_redirect = LOGOUT_REDIRECT || '/user/logged_out_redirect';

    if( session_user == null || session_token == null ){
      return;
    }

    // TODO: improve check for all domains being logged out?? fallback to tries/time??
    let _index = 1;
    const _max = Object.keys(language_domains).length;

    for( let [_lang, _lang_domains] of Object.entries(language_domains) ){
      let targetDomain = domain_scheme + '://' + _lang_domains[0];
      let logoutWindow = window.open(targetDomain + '/user/language_domain_logout', '', 'width=700,height=500');
      let checkInterval = setInterval(function(){
        logoutWindow.postMessage(
          {
            'logout_receiver_ready': false,
          },
          targetDomain
        )
      }, 250);

      window.addEventListener('message', function(_event){

        if( ! Array.prototype.includes.call(trusted_domains, _event.origin) ){
          return;
        }

        if( typeof _event.data.logout_receiver_ready == 'undefined' && typeof _event.data.logout_successful == 'undefined' ){
          return;
        }

        if( _event.data.logout_receiver_ready ){
          clearInterval(checkInterval);
          checkInterval = false;
          logoutWindow.postMessage(
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

        if( typeof _event.data.logout_successful != 'undefined' ){
          logoutWindow.close();
          if( _index >= _max ){
            let tokenFieldName = $('meta[name="csrf_field_name"]').attr('content');
            let tokenValue = $('meta[name="' + tokenFieldName + '"]').attr('content');
            data = {
              'session_user': session_user,
              'session_token': session_token,
            };
            data[tokenFieldName] = tokenValue;

            $.ajax({
              'url': '/user/domain_logout',
              'type': 'POST',
              'dataType': 'JSON',
              'data': data,
              'complete': function(_data){
                if( _data.responseJSON ){  // we have response JSON
                  if( _data.responseJSON.success ){  // successful format guess
                    setTimeout(function(){
                      window.location.assign(logout_redirect);
                    }, 250);
                  }else{  // validation error
                    setTimeout(function(){
                      window.location.assign(logout_redirect);
                    }, 250);
                  }
                }else{  // fully flopped ajax request
                  setTimeout(function(){
                    window.location.assign(logout_redirect);
                  }, 250);
                }
              }
            });
          }
          _index++;
        }

      });

    }

  });

});