window.addEventListener('load', function(){

  $(document).ready(function(){

    const session_user = SESSION_USER || null;
    const session_token = SESSION_TOKEN || null;
    const requester_domain = REQUESTER_DOMAIN || null;
    const domain_scheme = DOMAIN_SCHEME || null;
    const language_domains = LANGUAGE_DOMAINS || {};

    if( session_user == null || session_token == null ){
      return;
    }

    for( let [_lang, _lang_domains] of Object.entries(language_domains) ){
      let targetDomain = domain_scheme + '://' + _lang_domains[0];
      let loginWindow = window.open(targetDomain + '/user/language_domain_login', '', 'width=700,height=500');
      // FIXME: get this data to the window....and then get a callback to close the window from window.opener...
      loginWindow.postMessage(
        {
          'session_user': session_user,
          'session_token': session_token,
          'target_domain': targetDomain,
          'target_language': _lang,
        },
        domain_scheme + '://' + requester_domain
      );
    }

  });

});